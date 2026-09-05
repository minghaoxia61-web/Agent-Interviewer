"""Mock LLM：在没有 API Key 时提供确定性的行为，保证全链路可演示、可测试。

实现原则：
- 简历解析 / 漏洞挖掘用规则化的启发式算法，输出结构与真实 LLM 完全一致；
- 面试问题来自模板 + 简历引用，追问梯度和真实模式同构；
- 评分由可解释的统计规则计算（AgentX 原则：确定性优先）。
"""
import re
from typing import Any, Callable, Dict, List, Optional

from app.core.rules import REASON_LABELS, VAGUE_WORDS

SELF_INTRO = "__SELF_INTRO__"

_MAGIC_NUM = re.compile(r"(提升|降低|下降|减少|缩短|提高)[了]?\s*(\d+(?:\.\d+)?)\s*%")
_FUZZY_SCALE = re.compile(r"(数倍|倍级|千万级|百万级|亿级|海量|大规模数据)")
_VAGUE_VERB = re.compile(r"^(参与|协助|配合|跟进|接触|了解)")
_BUZZWORDS = ["微服务", "高并发", "分布式", "中间件", "云原生", "高可用", "大数据", "分布式锁"]


def emit_text(text: str, emit: Optional[Callable[[str], None]]) -> None:
    """把整段文本切成小块推给流式回调（Mock 流式输出）。"""
    if not emit:
        return
    for i in range(0, len(text), 8):
        emit(text[i : i + 8])


# ---------------------------------------------------------------------------
# 简历结构化（启发式）
# ---------------------------------------------------------------------------
def parse_resume(text: str, target_position: str) -> Dict[str, Any]:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    result: Dict[str, Any] = {
        "name": "",
        "target_position": target_position,
        "summary": "",
        "skills": [],
        "projects": [],
        "experiences": [],
        "education": [],
        "raw_text_chars": len(text or ""),
    }
    if not lines:
        return result

    result["name"] = re.sub(r"^#{1,6}\s*", "", lines[0]).strip()[:20]
    section = ""
    current: Optional[Dict[str, Any]] = None

    for raw in lines:
        line = re.sub(r"^#{1,6}\s*", "", raw).strip()
        is_bullet = bool(re.match(r"^[-•·*]\s+", line))
        content = re.sub(r"^[-•·*]\s+", "", line).strip()
        header_like = len(line) <= 30

        if "技能" in line and header_like:
            section, current = "skills", None
            continue
        if ("项目" in line and header_like) or re.match(r"^project\b", line, re.I):
            section = "projects"
            name = re.sub(r"^项目[一二三四五0-9]*[:：]?\s*", "", content)
            current = {"name": name or content, "role": "", "period": "", "stack": [], "highlights": []}
            result["projects"].append(current)
            continue
        if "教育" in line and header_like:
            section, current = "education", None
            continue
        if ("实习" in line or "工作经历" in line or "工作" in line) and header_like:
            section, current = "experiences", None
            continue

        if section == "skills" and content:
            parts = re.split(r"[、,，;；/]", content)
            for p in parts:
                p = re.sub(r"^(熟悉|精通|掌握|了解|熟练使用)[:：]?\s*", "", p).strip()
                if p and len(p) <= 20:
                    result["skills"].append(p)
        elif section == "projects" and current is not None:
            if is_bullet or current["highlights"] or len(content) > 25:
                current["highlights"].append(content)
            elif not current["role"] and ("负责" in content or "角色" in content):
                current["role"] = content
            else:
                current["highlights"].append(content)
        elif section == "education" and content:
            result["education"].append(content)
        elif section == "experiences" and content:
            result["experiences"].append(content)

    for proj in result["projects"]:
        stack_hits = []
        for kw in ["FastAPI", "Django", "Flask", "Spring", "MySQL", "Redis", "Kafka", "MongoDB",
                   "Celery", "Docker", "Kubernetes", "Scrapy", "Go", "Python", "Java", "gRPC", "RabbitMQ"]:
            if any(kw.lower() in h.lower() for h in proj["highlights"]) or \
               any(kw.lower() == s.lower() for s in result["skills"]):
                stack_hits.append(kw)
        proj["stack"] = stack_hits[:8]

    result["summary"] = f"候选人共 {len(result['projects'])} 个项目经历，技能 {len(result['skills'])} 项。"
    return result


# ---------------------------------------------------------------------------
# 漏洞挖掘（启发式，与 RESUME_DIG_SYSTEM 的维度一一对应）
# ---------------------------------------------------------------------------
def dig_weaknesses(resume: Dict[str, Any]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    seen_quotes = set()

    def add(dimension: str, quote: str, reason: str, probe_angle: str) -> None:
        quote = quote.strip()
        if quote and quote not in seen_quotes:
            seen_quotes.add(quote)
            found.append({"dimension": dimension, "quote": quote, "reason": reason, "probe_angle": probe_angle})

    for proj in resume.get("projects", []):
        for h in proj.get("highlights", []):
            m = _MAGIC_NUM.search(h)
            if m:
                add(
                    "magic_number", h,
                    f"声称「{m.group(0)}」但没有给出优化前的基线数据、测量方法，也没有说明提升来自哪一项改动，数字越漂亮越需要验证。",
                    "这个百分比的基线是多少？用什么工具测的？提升主要来自哪一处改动？",
                )
                continue
            if _FUZZY_SCALE.search(h):
                add(
                    "missing_metric", h,
                    "用「数倍 / 千万级」等模糊量词描述规模，没有任何精确度量，无法判断真实复杂度。",
                    "具体的数据量级是多少？这个规模的瓶颈出现在哪里？",
                )
                continue
            if _VAGUE_VERB.search(h):
                add(
                    "vague_scope", h,
                    "以「参与 / 协助」开头，看不出你本人具体负责的边界与产出，存在团队成果个人化的嫌疑。",
                    "在这个专项里你本人具体写了哪些部分？产出物是什么？",
                )
                continue
            hits = [w for w in _BUZZWORDS if w in h]
            if hits and not re.search(r"\d", h):
                add(
                    "buzzword_stack", h,
                    f"提到「{'/'.join(hits)}」但没有讲清选型动机、替代方案与权衡过程，属于名词堆砌高发区。",
                    f"为什么选择{hits[0]}？当时对比过哪些替代方案，为什么放弃？",
                )

    if len(found) < 3:
        skills = resume.get("skills", [])
        if skills:
            add(
                "buzzword_stack",
                f"技能：{'、'.join(skills)[:60]}",
                "技能列表覆盖面广但缺少深度佐证，需要抽验真实掌握程度。",
                "这些技能里你最熟悉哪一个？它底层的核心机制是什么？",
            )
    return found[:3]


# ---------------------------------------------------------------------------
# 面试对话模板
# ---------------------------------------------------------------------------
def intro_message(resume: Dict[str, Any], weaknesses: List[Dict[str, Any]], target_position: str) -> str:
    n = len(weaknesses)
    return (
        f"你好，我是今天的模拟面试官，面试岗位是「{target_position or '后端开发'}」。\n\n"
        f"我已经通读了你的简历，标记了 {n} 个需要深挖的点。流程是：先聊项目，再考察技术基础，"
        f"最后有一轮压力测试，全程我会像真实面试官一样打破砂锅问到底。\n\n"
        "先请你做一个简单的自我介绍，重点讲你最有代表性的一个项目。"
    )


def probe_question(weakness: Dict[str, Any]) -> str:
    return (
        f"我看到简历里写着：「{weakness['quote']}」。\n"
        f"{weakness['probe_angle']} 请具体讲讲。"
    )


_FOLLOWUP_LADDER = [
    "能展开讲讲当时的具体实现吗？你本人负责哪一部分，产出物是什么？",
    "这个方案为什么这么选？当时对比过哪些替代方案，分别为什么放弃？",
    "假设数据量和流量再放大 100 倍，这套方案最先在哪里撑不住？你会怎么改造？",
    "如果事后发现这个数字/结论是错的，最可能错在哪个环节？",
]


def followup_question(question: str, answer: str, depth: int, max_depth: int, reasons: List[str]) -> str:
    label = "；".join(REASON_LABELS.get(r, r) for r in reasons) or "细节不足"
    base = _FOLLOWUP_LADDER[min(depth - 1, len(_FOLLOWUP_LADDER) - 1)]
    return f"{base}（追问 {depth}/{max_depth}，因为：{label}）"


def drill_question(entry: Dict[str, Any]) -> str:
    prefix = f"[{entry.get('company', '大厂')}真题·{entry.get('category', '基础')}]" if entry.get("id") else ""
    return f"{prefix} {entry['question']}" if prefix else entry["question"]


def stress_question(quote: str, scenario: str) -> str:
    return (
        f"压力测试环节。回到你之前提到的「{quote}」——\n"
        f"如果{scenario}请具体推演一遍，不确定的地方直接说不确定。"
    )


def practice_eval(question: str, answer: str) -> Dict[str, Any]:
    """Mock 教练批改：确定性规则打分（真实模式由 LLM 生成参考要点）。"""
    from app.core.rules import assess_answer

    solid, reasons = assess_answer(answer)
    score = 7.5 if solid else max(2.0, 6.0 - len(reasons) * 1.5)
    return {
        "score": round(min(10.0, max(0.0, score)), 1),
        "strengths": ["回答了题目的核心方向"] if solid else [],
        "gaps": [REASON_LABELS.get(r, r) for r in reasons] or ["缺少展开细节"],
        "reference": ["（Mock 模式无参考答案要点，配置真实 LLM 后由模型生成）"],
        "mode": "mock",
    }


# ---------------------------------------------------------------------------
# 评估（统计规则，可解释）
# ---------------------------------------------------------------------------
def judge(transcript: List[Dict[str, Any]], stats: Dict[str, Any]) -> Dict[str, Any]:
    answers = [t for t in transcript if t.get("answer")]
    n = len(answers) or 1
    quant = sum(1 for t in answers if re.search(r"\d", t["answer"]))
    causal = sum(1 for t in answers if any(w in t["answer"] for w in ["因为", "所以", "由于", "因此", "导致", "从而"]))
    hedge = sum(1 for t in answers if sum(1 for w in VAGUE_WORDS if w in t["answer"]) >= 2)
    structure = sum(1 for t in answers if any(w in t["answer"] for w in ["首先", "其次", "然后", "最后", "第一", "第二", "步骤"]))
    eng_words = sum(1 for t in answers if any(w in t["answer"] for w in ["测试", "监控", "告警", "降级", "回滚", "日志", "压测"]))

    def clamp(x: float) -> float:
        return round(max(1.0, min(9.5, x)), 1)

    longest = max((a["answer"] for a in answers), key=len, default="")
    scores = {
        "technical_depth": clamp(3.5 + quant / n * 4 + causal / n * 1.5 + min(stats.get("probe_depth_max", 0), 3) * 0.3),
        "logic_rigor": clamp(3.5 + causal / n * 5 - hedge / n * 2.5),
        "engineering_quality": clamp(3.5 + quant / n * 3 + min(eng_words, 4) * 0.75),
        "communication": clamp(4.0 + structure / n * 3 + min(len(longest) / 150, 1.5)),
        "resilience": clamp(8.0 - hedge / n * 4 - stats.get("followup_exhausted", 0) * 1.5),
    }

    def pick(pred) -> Optional[Dict[str, Any]]:
        for t in answers:
            if pred(t):
                return {"turn": t["turn"], "quote": t["answer"][:120], "comment": "轨迹原文摘录"}
        return None

    evidence = {
        "technical_depth": pick(lambda t: re.search(r"\d", t["answer"]) is not None and len(t["answer"]) > 60),
        "logic_rigor": pick(lambda t: any(w in t["answer"] for w in ["因为", "所以", "因此"])),
        "engineering_quality": pick(lambda t: any(w in t["answer"] for w in ["测试", "监控", "压测", "日志"])),
        "communication": pick(lambda t: any(w in t["answer"] for w in ["首先", "其次", "然后", "最后"])),
        "resilience": pick(lambda t: t.get("decision") == "follow_up"),
    }
    evidence = {k: v for k, v in evidence.items() if v}

    dim_labels = {
        "technical_depth": "技术深度", "logic_rigor": "逻辑严谨", "engineering_quality": "工程素养",
        "communication": "沟通表达", "resilience": "抗压应变",
    }
    suggestions = []
    for key, label in dim_labels.items():
        s = scores[key]
        if key == "technical_depth":
            text = "回答尽量带上具体数字、数据规模和实现细节；每讲一个结论，补一句『因为……所以……』。" if s < 7 else "技术深度达标，下一步可以主动讲技术权衡与替代方案，展示架构判断力。"
        elif key == "logic_rigor":
            text = "减少『可能/大概』这类模糊措辞，先给结论再给因果链路，不确定的部分明确说不确定。" if s < 7 else "逻辑链路完整，注意在结尾主动收束结论。"
        elif key == "engineering_quality":
            text = "补充工程侧词汇：怎么测试、怎么监控、出了问题怎么降级回滚，这些是面试官判断真实项目经验的关键信号。" if s < 7 else "工程素养表现良好，可再强调量化收益（如错误率、耗时变化）。"
        elif key == "communication":
            text = "用『第一…第二…』结构化表达，每个回答控制在 1-2 分钟，先结论后展开。" if s < 7 else "表达结构清晰，保持。"
        else:
            text = "被追问时不要回避，正面承认不知道再给推理路径，比含糊过去更加分。" if s < 7 else "抗压表现稳定，追问下仍能给出实质内容。"
        suggestions.append({"dimension": key, "label": label, "text": text})

    summary = (
        f"共 {len(answers)} 轮有效问答，含量化描述的回答占 {quant * 100 // n}%，"
        f"最大追问深度 {stats.get('probe_depth_max', 0)} 层。"
        + ("整体偏名词化表达，缺少可验证的细节。" if scores["technical_depth"] < 6 else "整体表达有细节、有推导，具备通过大厂基础面的潜质。")
    )
    return {"scores": scores, "evidence": evidence, "suggestions": suggestions, "summary": summary}
