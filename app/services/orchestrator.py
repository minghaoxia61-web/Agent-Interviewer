"""编排层：连接 会话存储 <-> LangGraph 状态机 <-> API 路由。

每个会话首次使用时编译一张图（图节点通过闭包持有会话依赖），
每轮对话 invoke 一次，并把结果回写到 Session、追加 Trace。
"""
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

from app.core.agents.graph import build_graph
from app.core.config import settings
from app.schemas.interview import STAGE_LABELS
from app.services.llm import LLMService
from app.services.rag.retriever import build_retriever
from app.services.reporter import ReportGenerator
from app.storage.session_store import STORE, Session

_PERSIST_FIELDS = ("focus_idx", "probe_depth", "current_question", "drill_rounds",
                   "stress_rounds", "finished", "report_md", "overall", "summary")
_PERSIST_LISTS = ("drill_asked", "vagueness_log", "scores")


class SessionNotFound(Exception):
    pass


class InterviewFinished(Exception):
    pass


class AnalysisInProgress(Exception):
    """简历 AI 分析（漏洞挖掘/体检诊断）仍在后台执行。"""
    pass


class InterviewOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.retriever = build_retriever(settings.knowledge_dir, settings.retriever_mode,
                                         chroma_dir=settings.data_dir / "chroma")
        self.reporter = ReportGenerator(self.llm)
        self.store = STORE
        # LangGraph SqliteSaver：图状态逐 checkpoint 落盘（进程重启后可从断点恢复）
        self.checkpointer = None
        if settings.use_checkpointer:
            try:
                import sqlite3 as _sqlite3

                from langgraph.checkpoint.sqlite import SqliteSaver

                self.checkpointer = SqliteSaver(_sqlite3.connect(
                    str(settings.data_dir / "checkpoints.db"), check_same_thread=False))
            except Exception as e:  # noqa: BLE001 - 未安装/版本不配时优雅降级
                print(f"[RAI] LangGraph checkpointer 不可用，降级为无检查点模式：{e}")

    # ------------------------------------------------------------------
    def _require(self, sid: str) -> Session:
        sess = self.store.get(sid)
        if sess is None:
            raise SessionNotFound(sid)
        return sess

    def _get_graph(self, sess: Session):
        if sess.graph is None:
            deps = SimpleNamespace(llm=self.llm, retriever=self.retriever,
                                   store=self.store, reporter=self.reporter, settings=settings)
            graph = build_graph(deps)
            # 持有 checkpointer 时才在此处编译；否则编译出无检查点版本
            sess.graph = (graph.compile(checkpointer=self.checkpointer)
                          if self.checkpointer else graph.compile())
        return sess.graph

    def _invoke(self, sess: Session, state: Dict[str, Any],
                emit: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        app = self._get_graph(sess)
        # emit 通过 configurable 传递（callable 不可被 checkpointer 序列化，不能进 state）
        config = {"recursion_limit": 60,
                  "configurable": {"thread_id": f"interview-{sess.id}", "emit": emit}}
        try:
            return app.invoke(state, config=config)
        except Exception as e:  # noqa: BLE001 - 图内异常统一上抛给路由层
            raise RuntimeError(f"面试状态机执行失败: {e}") from e

    def _persist(self, sess: Session, result: Dict[str, Any]) -> None:
        sess.stage = result.get("stage", sess.stage)
        for f in _PERSIST_FIELDS:
            if f in result:
                setattr(sess, f, result[f])
        for f in _PERSIST_LISTS:
            if f in result:
                setattr(sess, f, result[f])
        self.store.save(sess)

    def _turn_response(self, sess: Session, result: Dict[str, Any],
                       stage_before: str) -> Dict[str, Any]:
        decision = result.get("decision") or None
        reasons = result.get("reasons") or []
        meta = {"decision": decision, "reasons": reasons,
                "probe_depth": result.get("probe_depth", sess.probe_depth)}
        assistant = result.get("assistant_msg", "")
        self.store.append_message(sess, "assistant", assistant, stage=sess.stage, meta=meta)
        user_turns = sum(1 for m in sess.messages if m["role"] == "user")
        self.store.append_trace(sess, {
            "turn": user_turns, "stage_before": stage_before, "stage_after": sess.stage,
            "assistant": assistant, "decision": decision, "reasons": reasons,
            "probe_depth": meta["probe_depth"], "drill_rounds": sess.drill_rounds,
            "stress_rounds": sess.stress_rounds,
        })
        return {
            "session_id": sess.id,
            "assistant_message": assistant,
            "stage": sess.stage,
            "stage_label": STAGE_LABELS.get(sess.stage, sess.stage),
            "decision": decision,
            "decision_reasons": reasons,
            "probe_depth": meta["probe_depth"],
            "total_turns": user_turns,
            "finished": sess.finished,
        }

    # ------------------------------------------------------------------
    def start(self, sid: str) -> Dict[str, Any]:
        sess = self._require(sid)
        if sess.finished:
            raise InterviewFinished(sid)
        if sess.analysis_status == "processing":
            raise AnalysisInProgress(sid)
        with sess.turn_lock:
            if sess.messages:  # 已开过场：直接返回当前状态，避免重复 intro
                user_turns = sum(1 for m in sess.messages if m["role"] == "user")
                return {
                    "session_id": sess.id, "assistant_message": "", "stage": sess.stage,
                    "stage_label": STAGE_LABELS.get(sess.stage, sess.stage), "decision": None,
                    "decision_reasons": [], "probe_depth": sess.probe_depth,
                    "total_turns": user_turns, "finished": sess.finished,
                }
            stage_before = sess.stage
            result = self._invoke(sess, {"session_id": sid, "stage": sess.stage, "last_user_msg": ""})
            self._persist(sess, result)
            return self._turn_response(sess, result, stage_before)

    def handle_message(self, sid: str, user_text: str,
                       emit: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        sess = self._require(sid)
        if sess.finished:
            raise InterviewFinished(sid)
        if not (user_text or "").strip():
            raise ValueError("消息不能为空")
        with sess.turn_lock:  # 同一会话串行化，防止并发 invoke 竞争状态
            if sess.finished:
                raise InterviewFinished(sid)
            stage_before = sess.stage
            self.store.append_message(sess, "user", user_text.strip(), stage=stage_before)
            self.store.append_trace(sess, {"turn": sum(1 for m in sess.messages if m["role"] == "user"),
                                           "event": "user_message", "user": user_text.strip(),
                                           "stage": stage_before})
            result = self._invoke(sess, {"session_id": sid, "stage": sess.stage,
                                         "last_user_msg": user_text.strip()}, emit=emit)
            self._persist(sess, result)
            return self._turn_response(sess, result, stage_before)

    # ------------------------------------------------------------------
    def finish(self, sid: str) -> Dict[str, Any]:
        """提前结束面试并生成报告（自然结束时由 evaluate 节点自动调用同一生成器）。"""
        sess = self._require(sid)
        with sess.turn_lock:
            if not sess.finished:
                result = self.reporter.generate(sess)
                sess.overall = result["overall"]
                sess.summary = result["summary"]
                sess.scores = result["scores"]
                sess.report_md = result["markdown"]
                sess.finished = True
                sess.stage = "end"
                self.store.save_report(sess, result["markdown"])
                self.store.append_trace(sess, {"event": "finish_early"})
        return self.report_payload(sid)

    def report_payload(self, sid: str) -> Dict[str, Any]:
        sess = self._require(sid)
        if not sess.finished:
            payload = self.finish(sid)
        else:
            payload = {
                "session_id": sess.id,
                "markdown": sess.report_md,
                "scores": sess.scores,
                "overall": sess.overall,
                "summary": sess.summary,
                "trace_file": sess.trace_file or None,
            }
        return payload

    def state_payload(self, sid: str) -> Dict[str, Any]:
        sess = self._require(sid)
        return {
            "session_id": sess.id,
            "stage": sess.stage,
            "stage_label": STAGE_LABELS.get(sess.stage, sess.stage),
            "target_position": sess.target_position,
            "total_turns": sum(1 for m in sess.messages if m["role"] == "user"),
            "probe_depth": sess.probe_depth,
            "focus_idx": sess.focus_idx,
            "weakness_count": len(sess.weaknesses),
            "drill_rounds": sess.drill_rounds,
            "stress_rounds": sess.stress_rounds,
            "finished": sess.finished,
            "diagnosis": sess.diagnosis,
            "filename": None,
            "messages": sess.messages,
        }


ORCHESTRATOR = InterviewOrchestrator()
