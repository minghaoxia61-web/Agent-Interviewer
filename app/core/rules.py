"""确定性评估规则（AgentX 原则：能用规则完成的事不调用 LLM）。

回答质量评估完全由规则驱动，触发原因随 Trace 落盘，
保证每一次"追问 vs 推进"的决策都是可证伪的。
"""
import re
from typing import List, Tuple

VAGUE_WORDS = ["可能", "大概", "应该", "差不多", "反正", "也许", "貌似", "好像", "一些", "很多", "数倍"]
CAUSAL_WORDS = ["因为", "所以", "由于", "因此", "导致", "于是", "从而", "原因"]
HEDGE_RATIO_THRESHOLD = 0.04  # 模糊词密度超过该值视为含糊

REASON_LABELS = {
    "answer_too_short": "回答过短，缺少实现细节",
    "no_numbers": "未给出任何量化数据或具体规模",
    "hedge_words": "模糊措辞过多，结论不可靠",
    "no_causal_chain": "缺少因果链路解释，只有结论没有推导",
}

# 知识库检索失败时的兜底技术题
GENERIC_DRILL_QUESTIONS = [
    "你简历里写的最熟悉的那门语言，它的内存管理机制是怎样的？出现内存泄漏时你怎么排查？",
    "数据库索引为什么能加快查询？什么情况下索引反而会变慢？",
    "线上接口突然变慢，你会按什么顺序排查？每一步看什么指标？",
    "进程和线程的区别是什么？你项目里为什么选择线程模型而不是进程模型？",
    "缓存和数据库的一致性你怎么保证？先更新数据库还是先删缓存，为什么？",
    "TCP 三次握手各一步分别解决了什么问题？两次握手会有什么风险？",
]

# 压力测试的极端场景库
STRESS_SCENARIOS = [
    "瞬时流量放大 100 倍，你的系统最先在哪里撑不住？",
    "下游依赖服务大面积超时，你的接口如何自保？",
    "发布过程中出现了数据不一致，用户已经看到错误数据，你怎么办？",
    "凌晨两点收到告警：主库 CPU 打满且持续上涨，描述你的处理动作。",
]


def assess_answer(text: str) -> Tuple[bool, List[str]]:
    """规则化评估回答是否扎实。

    返回 (is_solid, reasons)。reasons 用稳定的英文 key，
    便于 Trace 落盘与报表统计，展示时再映射为中文标签。
    """
    t = (text or "").strip()
    reasons: List[str] = []

    if len(t) < 30:
        reasons.append("answer_too_short")
    if not re.search(r"\d", t):
        reasons.append("no_numbers")

    hedges = [w for w in VAGUE_WORDS if w in t]
    if hedges and len(hedges) / max(len(t), 1) > HEDGE_RATIO_THRESHOLD * 10:
        reasons.append("hedge_words")
    elif len(hedges) >= 2:
        reasons.append("hedge_words")

    if len(t) >= 30 and not any(w in t for w in CAUSAL_WORDS):
        reasons.append("no_causal_chain")

    # 单一规则触发即判为不扎实，但过短回答只按过短处理，避免误伤
    if len(t) < 30:
        return False, ["answer_too_short"]
    return (len(reasons) == 0), reasons


def reasons_label(reasons: List[str]) -> str:
    return "；".join(REASON_LABELS.get(r, r) for r in reasons) or "无"
