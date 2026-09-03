"""报告生成器：Judge 产出内容，代码负责结构与落盘（内容与版式解耦）。"""
from typing import Any, Dict, List

from app.core.rules import REASON_LABELS
from app.schemas.report import DimensionScore

DIM_KEYS = ["technical_depth", "logic_rigor", "engineering_quality", "communication", "resilience"]
DIM_LABELS = {
    "technical_depth": "技术深度", "logic_rigor": "逻辑严谨", "engineering_quality": "工程素养",
    "communication": "沟通表达", "resilience": "抗压应变",
}
STAGE_LABELS = {
    "intro": "开场", "project_probing": "项目深挖", "tech_drill": "技术基础",
    "stress_test": "压力测试", "evaluation": "评估", "end": "结束",
}


class ReportGenerator:
    def __init__(self, llm) -> None:
        self.llm = llm

    def build_transcript(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把消息流折叠成 (问题, 回答, 决策) 轨迹。"""
        transcript: List[Dict[str, Any]] = []
        pending_question: Dict[str, Any] = {}
        for msg in messages:
            if msg["role"] == "assistant":
                pending_question = msg
            elif msg["role"] == "user" and pending_question:
                meta = pending_question.get("meta", {})
                transcript.append({
                    "turn": msg["turn"] - 1,
                    "stage": pending_question.get("stage", ""),
                    "question": pending_question["content"],
                    "answer": msg["content"],
                    "decision": meta.get("decision"),
                    "reasons": meta.get("reasons", []),
                    "depth": meta.get("probe_depth", 0),
                })
                pending_question = {}
        return transcript

    def generate(self, session) -> Dict[str, Any]:
        transcript = self.build_transcript(session.messages)
        followups = [t for t in transcript if t.get("decision") == "follow_up"]
        stats = {
            "target_position": session.target_position,
            "probe_rounds": sum(1 for t in transcript if t.get("stage") == "project_probing"),
            "drill_rounds": sum(1 for t in transcript if t.get("stage") == "tech_drill"),
            "stress_rounds": sum(1 for t in transcript if t.get("stage") == "stress_test"),
            "probe_depth_max": max((t.get("depth", 0) for t in transcript), default=0),
            "followup_exhausted": sum(1 for t in transcript
                                      if t.get("decision") == "advance" and t.get("reasons")),
        }
        judge = self.llm.judge(transcript, stats)
        raw_scores: Dict[str, float] = judge.get("scores", {})
        scores: List[Dict[str, Any]] = []
        for key in DIM_KEYS:
            scores.append({
                "key": key, "label": DIM_LABELS[key],
                "score": round(float(raw_scores.get(key, 0)), 1),
            })
        overall = round(sum(s["score"] for s in scores) / len(scores), 1)

        evidence = judge.get("evidence", {})
        suggestions = judge.get("suggestions", [])
        summary = judge.get("summary", "")

        markdown = self._render_markdown(session, scores, overall, summary, evidence,
                                         suggestions, transcript, stats, followups)
        return {"markdown": markdown, "scores": scores, "overall": overall,
                "summary": summary, "evidence": evidence, "suggestions": suggestions}

    def _render_markdown(self, session, scores, overall, summary, evidence, suggestions,
                         transcript, stats, followups) -> str:
        lines: List[str] = []
        lines.append("# RAI 模拟面试评估报告")
        lines.append("")
        lines.append(f"- **候选人**：{session.resume.get('name') or '未署名'}")
        lines.append(f"- **目标岗位**：{session.target_position or '未指定'}")
        lines.append(f"- **面试时间**：{session.created_at}")
        lines.append(f"- **评估模式**：{'LLM-as-a-Judge（真实 LLM）' if not self.llm.mock else '确定性规则评估（Mock 模式）'}")
        lines.append(f"- **综合得分**：**{overall} / 10**")
        lines.append("")
        lines.append("## 一、总评")
        lines.append("")
        lines.append(summary or "（无）")
        lines.append("")
        lines.append("## 二、维度得分（雷达图数据）")
        lines.append("")
        lines.append("| 维度 | 得分 |")
        lines.append("| --- | --- |")
        for s in scores:
            lines.append(f"| {s['label']} | {s['score']} |")
        lines.append("")
        lines.append("## 三、关键证据")
        lines.append("")
        if evidence:
            for key in DIM_KEYS:
                items = evidence.get(key) or []
                if not isinstance(items, list):
                    items = [items]
                for it in items:
                    if isinstance(it, dict) and it.get("quote"):
                        lines.append(f"- **{DIM_LABELS[key]}**（第 {it.get('turn', '?')} 轮）：「{it.get('quote')}」 {it.get('comment', '')}")
        else:
            lines.append("- 无有效证据引用。")
        lines.append("")
        lines.append("## 四、追问复盘（可证伪轨迹）")
        lines.append("")
        if followups:
            for t in followups:
                labels = "；".join(REASON_LABELS.get(r, r) for r in t.get("reasons", [])) or "细节不足"
                lines.append(
                    f"- 第 {t['turn']} 轮【{STAGE_LABELS.get(t.get('stage'), t.get('stage'))}】"
                    f"触发第 {t.get('depth', '?')} 层追问，规则判定：{labels}。"
                )
        else:
            lines.append("- 全程未触发追问：所有回答均通过确定性规则检查（长度、量化、因果链、模糊词）。")
        lines.append(f"- 规则触发统计：追问 {len(followups)} 次；压力测试 {stats['stress_rounds']} 轮；"
                     f"技术基础 {stats['drill_rounds']} 轮；最大追问深度 {stats['probe_depth_max']} 层。")
        lines.append("")
        lines.append("## 五、优化建议")
        lines.append("")
        for s in suggestions:
            label = s.get("label") or DIM_LABELS.get(s.get("dimension"), s.get("dimension"))
            lines.append(f"- **{label}**：{s.get('text', '')}")
        lines.append("")
        lines.append("## 六、可证伪性说明")
        lines.append("")
        lines.append("- 本报告所有分数均可回溯：逐轮对话轨迹（含每条追问的规则触发原因）保存在 Trace JSONL 文件中；")
        lines.append("- 「追问 vs 推进」的判断由确定性规则（answer_too_short / no_numbers / hedge_words / no_causal_chain）驱动，"
                     "规则代码位于 `app/core/rules.py`，任何人可复核；")
        lines.append("- 评估维度与分值纪律见 `app/core/prompts.py` 中的 JUDGE_SYSTEM。")
        return "\n".join(lines)


def to_dimension_models(scores: List[Dict[str, Any]]) -> List[DimensionScore]:
    return [DimensionScore(**s) for s in scores]
