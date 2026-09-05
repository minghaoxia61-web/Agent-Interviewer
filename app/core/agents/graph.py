"""LangGraph 动态追问状态机（Adaptive DAG）。

状态流转（一次完整面试）：
    START -> intro -> (候选人自我介绍) -> project_probing -> tech_drill
          -> stress_test -> evaluation -> END

每轮用户发言 = 一次 graph.invoke：
- 各阶段节点用确定性规则（assess_answer）决定「追问 follow_up」或「推进 advance」；
- 跨阶段推进通过条件边在同一轮内链式完成，保证用户每次发言后都能拿到下一条问题；
- 「追问 vs 推进」的每次决策及触发原因都随 Trace 落盘，可证伪。
"""
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langchain_core.runnables import RunnableConfig

from langgraph.graph import END, START, StateGraph

from app.core.rules import GENERIC_DRILL_QUESTIONS, STRESS_SCENARIOS, assess_answer

STAGE_INTRO = "intro"
STAGE_PROBE = "project_probing"
STAGE_DRILL = "tech_drill"
STAGE_STRESS = "stress_test"
STAGE_EVAL = "evaluation"
STAGE_END = "end"

# intro 环节的问题哨兵：用户回答它之后，probe 节点开始第一个疑点提问
SELF_INTRO = "__SELF_INTRO__"


def _emit_from(config: Any) -> Optional[Callable[[str], None]]:
    """emit 回调经 runnable config 传递（callable 不能进 checkpoint 序列化的 state）。"""
    try:
        return (config or {}).get("configurable", {}).get("emit")
    except Exception:
        return None


class InterviewState(TypedDict, total=False):
    # 输入
    session_id: str
    last_user_msg: str
    # 阶段内流转的瞬态标记（仅单次 invoke 内存活，不落盘）
    drill_first: bool
    stress_first: bool
    pending_ack: str             # 跨阶段衔接的过渡语，由下一阶段节点拼在问题前
    # 节点输出
    assistant_msg: str
    decision: str                # follow_up / advance / advance_stage / ""
    reasons: List[str]
    # 以下字段由编排层回写到 Session 持久化
    stage: str
    focus_idx: int
    probe_depth: int
    current_question: str
    drill_rounds: int
    drill_asked: List[str]
    stress_rounds: int
    vagueness_log: List[Dict[str, Any]]
    finished: bool
    report_md: str
    scores: List[Dict[str, Any]]
    overall: float
    summary: str


def build_graph(deps):
    """deps: 提供 llm / retriever / store / reporter / settings 的命名空间。"""
    llm, retriever, store = deps.llm, deps.retriever, deps.store
    s = deps.settings

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------
    def _pick_drill(sess, emit=None):
        """RAG 检索下一道技术基础题；知识库未命中时回落到通用题库。"""
        skills = " ".join((sess.resume.get("skills") or [])[:6])
        query = f"{skills} {sess.target_position or ''}".strip() or "后端开发 基础"
        entry = retriever.pick(query, exclude=list(sess.drill_asked))
        if entry:
            return llm.drill_question(entry, sess.target_position, emit=emit), entry["id"]
        idx = len(sess.drill_asked) % len(GENERIC_DRILL_QUESTIONS)
        return GENERIC_DRILL_QUESTIONS[idx], f"generic_{idx}"

    def _pick_stress_quote(sess) -> str:
        """压力测试引用最薄弱的历史回答；没有则引用当前疑点原文。"""
        if sess.vagueness_log:
            worst = max(sess.vagueness_log, key=lambda v: len(v.get("reasons", [])))
            return worst.get("quote", "")
        if sess.weaknesses:
            w = sess.weaknesses[min(sess.focus_idx, len(sess.weaknesses) - 1)]
            return w.get("quote", "")
        return "你项目里的核心设计"

    def _log_vagueness(sess, stage: str, answer: str, reasons: List[str]):
        return sess.vagueness_log + [{"stage": stage, "quote": answer[:80], "reasons": reasons}]

    # ------------------------------------------------------------------
    # 节点
    # ------------------------------------------------------------------
    def intro_node(state: Dict[str, Any], config: RunnableConfig = None) -> Dict[str, Any]:
        sess = store.get(state["session_id"])
        msg = llm.intro_message(sess.resume, sess.weaknesses, sess.target_position, emit=_emit_from(config))
        return {
            "assistant_msg": msg,
            "stage": STAGE_PROBE,
            "focus_idx": 0,
            "probe_depth": 0,
            "current_question": SELF_INTRO,
            "decision": "",
            "reasons": [],
        }

    def probe_node(state: Dict[str, Any], config: RunnableConfig = None) -> Dict[str, Any]:
        sess = store.get(state["session_id"])
        emit = _emit_from(config)
        answer = (state.get("last_user_msg") or "").strip()
        weaknesses = sess.weaknesses or []

        # 自我介绍之后的第一个疑点提问（不评估自我介绍本身）
        if sess.current_question == SELF_INTRO:
            if weaknesses:
                q = llm.probe_question(weaknesses[0], sess.target_position, emit=emit)
                return {"assistant_msg": q, "decision": "advance", "reasons": [],
                        "current_question": q, "focus_idx": 0, "probe_depth": 0}
            return {"assistant_msg": "简历中没有标记出可深挖的项目疑点，我们直接进入技术基础环节。",
                    "stage": STAGE_DRILL, "drill_first": True,
                    "pending_ack": "先从第一道基础题开始。",
                    "decision": "advance_stage", "reasons": []}

        solid, reasons = assess_answer(answer)
        has_next = (sess.focus_idx + 1 < len(weaknesses)) and (sess.focus_idx + 1 < s.max_probe_weaknesses)

        # 追问：回答不扎实且未到追问层数上限
        if not solid and sess.probe_depth < s.max_followup_depth:
            depth = sess.probe_depth + 1
            q = llm.followup_question(sess.current_question, answer, depth, reasons,
                                      sess.target_position, emit=emit)
            return {"assistant_msg": q, "decision": "follow_up", "reasons": reasons,
                    "probe_depth": depth, "current_question": q,
                    "vagueness_log": _log_vagueness(sess, STAGE_PROBE, answer, reasons)}

        # 推进：下一个疑点 / 进入技术基础
        ack = "好，这个点你讲得比较扎实。" if solid else "好，这一点先问到这。"
        if has_next:
            q = llm.probe_question(weaknesses[sess.focus_idx + 1], sess.target_position, emit=emit)
            return {"assistant_msg": f"{ack}\n\n{q}", "decision": "advance",
                    "reasons": [] if solid else reasons,
                    "focus_idx": sess.focus_idx + 1, "probe_depth": 0, "current_question": q}
        return {"assistant_msg": f"{ack}\n\n项目环节就聊到这里，接下来考察技术基础。",
                "stage": STAGE_DRILL, "drill_first": True,
                "pending_ack": "先从第一道基础题开始。",
                "decision": "advance_stage", "reasons": [] if solid else reasons}

    def drill_node(state: Dict[str, Any], config: RunnableConfig = None) -> Dict[str, Any]:
        sess = store.get(state["session_id"])
        emit = _emit_from(config)
        answer = (state.get("last_user_msg") or "").strip()

        if state.get("drill_first"):
            q, entry_id = _pick_drill(sess, emit)
            return {"assistant_msg": f"{state.get('pending_ack', '')}{q}", "pending_ack": "",
                    "decision": "advance_stage", "reasons": [], "current_question": q,
                    "drill_rounds": 1, "drill_asked": sess.drill_asked + [entry_id]}

        solid, reasons = assess_answer(answer)
        log = _log_vagueness(sess, STAGE_DRILL, answer, reasons) if not solid else sess.vagueness_log

        if sess.drill_rounds >= s.max_drill_rounds:
            return {"assistant_msg": "技术基础就到这里，最后进入压力测试环节。",
                    "stage": STAGE_STRESS, "stress_first": True,
                    "pending_ack": "别紧张，这一轮考察的是极限场景下的判断力。",
                    "decision": "advance_stage", "reasons": [] if solid else reasons,
                    "vagueness_log": log}

        q, entry_id = _pick_drill(sess, emit)
        return {"assistant_msg": q, "decision": "advance", "reasons": [] if solid else reasons,
                "current_question": q, "drill_rounds": sess.drill_rounds + 1,
                "drill_asked": sess.drill_asked + [entry_id], "vagueness_log": log}

    def stress_node(state: Dict[str, Any], config: RunnableConfig = None) -> Dict[str, Any]:
        sess = store.get(state["session_id"])
        emit = _emit_from(config)
        answer = (state.get("last_user_msg") or "").strip()

        if state.get("stress_first"):
            scenario = STRESS_SCENARIOS[sess.stress_rounds % len(STRESS_SCENARIOS)]
            q = llm.stress_question(_pick_stress_quote(sess), scenario, sess.target_position, emit=emit)
            return {"assistant_msg": f"{state.get('pending_ack', '')}{q}", "pending_ack": "",
                    "decision": "advance_stage", "reasons": [], "current_question": q,
                    "stress_rounds": sess.stress_rounds + 1}

        solid, reasons = assess_answer(answer)
        log = _log_vagueness(sess, STAGE_STRESS, answer, reasons) if not solid else sess.vagueness_log

        if sess.stress_rounds >= s.max_stress_rounds:
            return {"assistant_msg": "好的，今天的面试就到这里。我正在基于完整对话轨迹生成评估报告……",
                    "stage": STAGE_EVAL, "decision": "advance_stage",
                    "reasons": [] if solid else reasons, "vagueness_log": log}

        scenario = STRESS_SCENARIOS[sess.stress_rounds % len(STRESS_SCENARIOS)]
        q = llm.stress_question(_pick_stress_quote(sess), scenario, sess.target_position, emit=emit)
        return {"assistant_msg": q, "decision": "advance", "reasons": [] if solid else reasons,
                "current_question": q, "stress_rounds": sess.stress_rounds + 1, "vagueness_log": log}

    def evaluate_node(state: Dict[str, Any]) -> Dict[str, Any]:
        sess = store.get(state["session_id"])
        result = deps.reporter.generate(sess)
        sess.overall = result["overall"]
        sess.summary = result["summary"]
        sess.scores = result["scores"]
        store.save_report(sess, result["markdown"])
        return {"assistant_msg": "", "stage": STAGE_END, "finished": True,
                "report_md": result["markdown"], "scores": result["scores"],
                "overall": result["overall"], "summary": result["summary"],
                "decision": "", "reasons": []}

    def noop_end(state: Dict[str, Any]) -> Dict[str, Any]:
        return {"assistant_msg": ""}

    # ------------------------------------------------------------------
    # 路由
    # ------------------------------------------------------------------
    def route_by_stage(state: Dict[str, Any]) -> str:
        return state.get("stage", STAGE_INTRO)

    def _stage_router(chain_to: Dict[str, str]):
        def router(state: Dict[str, Any]) -> str:
            stage = state.get("stage")
            if stage == STAGE_EVAL:
                return "evaluate"
            if stage in chain_to:
                return chain_to[stage]
            return "done"
        return router

    g = StateGraph(InterviewState)
    g.add_node("intro", intro_node)
    g.add_node("probe", probe_node)
    g.add_node("drill", drill_node)
    g.add_node("stress", stress_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("noop_end", noop_end)

    g.add_conditional_edges(START, route_by_stage, {
        STAGE_INTRO: "intro", STAGE_PROBE: "probe", STAGE_DRILL: "drill",
        STAGE_STRESS: "stress", STAGE_EVAL: "evaluate", STAGE_END: "noop_end",
    })
    g.add_edge("intro", END)
    g.add_conditional_edges("probe", _stage_router({STAGE_DRILL: "drill"}),
                            {"drill": "drill", "evaluate": "evaluate", "done": END})
    g.add_conditional_edges("drill", _stage_router({STAGE_STRESS: "stress"}),
                            {"stress": "stress", "evaluate": "evaluate", "done": END})
    g.add_conditional_edges("stress", _stage_router({}),
                            {"evaluate": "evaluate", "done": END})
    g.add_edge("evaluate", END)
    g.add_edge("noop_end", END)

    # 编译交由 orchestrator 完成（按需注入 SqliteSaver checkpointer）
    return g
