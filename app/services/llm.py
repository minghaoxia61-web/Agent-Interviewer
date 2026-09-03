"""LLM 服务层：统一封装真实 LLM 调用与 Mock 模式分发。

- 未配置 LLM_API_KEY 时自动进入 Mock 模式（确定性输出，全流程可跑通）；
- 高层方法（parse_resume / dig_weaknesses / 面试话术 / judge）对上层屏蔽模式差异；
- emit 回调用于 WebSocket 流式输出。
"""
import json
import re
from typing import Any, Callable, Dict, List, Optional

from app.core import prompts
from app.core.config import settings
from app.services import mock_llm


class LLMError(RuntimeError):
    """真实 LLM 调用失败（网络/鉴权/限流等）。"""


class LLMService:
    def __init__(self) -> None:
        self.mock = not settings.llm_api_key.strip()
        self._client = None
        if not self.mock:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout,
            )

    # ------------------------------------------------------------------
    # 底层调用
    # ------------------------------------------------------------------
    def chat(self, system: str, user: str, temperature: Optional[float] = None,
             emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            raise LLMError("mock mode has no raw chat")
        kwargs: Dict[str, Any] = dict(
            model=settings.llm_model,
            temperature=settings.llm_temperature if temperature is None else temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        try:
            if emit:
                kwargs["stream"] = True
                chunks: List[str] = []
                for event in self._client.chat.completions.create(**kwargs):
                    delta = getattr(event.choices[0], "delta", None)
                    piece = getattr(delta, "content", None) if delta else None
                    if piece:
                        chunks.append(piece)
                        emit(piece)
                return "".join(chunks)
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001 - 统一转成业务异常
            raise LLMError(f"LLM 调用失败: {e}") from e

    @staticmethod
    def _extract_json(raw: str) -> Any:
        """宽松 JSON 提取：容忍 markdown 代码块与前后的说明文字。"""
        text = (raw or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            if start == -1:
                continue
            try:
                return json.JSONDecoder().raw_decode(text[start:], 0)[0]
            except json.JSONDecodeError:
                continue
        raise ValueError(f"无法从 LLM 输出中解析 JSON: {text[:200]}")

    # ------------------------------------------------------------------
    # 简历：解析 + 漏洞挖掘
    # ------------------------------------------------------------------
    def parse_resume(self, text: str, target_position: str) -> Dict[str, Any]:
        if self.mock:
            return mock_llm.parse_resume(text, target_position)
        user = prompts.RESUME_PARSE_USER_TMPL.format(
            target_position=target_position or "未指定", resume_text=text[:8000]
        )
        data = self._extract_json(self.chat(prompts.RESUME_PARSE_SYSTEM, user, temperature=0.1))
        data.setdefault("target_position", target_position)
        data.setdefault("raw_text_chars", len(text))
        return data

    def dig_weaknesses(self, resume: Dict[str, Any]) -> List[Dict[str, Any]]:
        if self.mock:
            return mock_llm.dig_weaknesses(resume)
        user = prompts.RESUME_DIG_USER_TMPL.format(
            target_position=resume.get("target_position") or "未指定",
            resume_json=json.dumps(resume, ensure_ascii=False)[:6000],
        )
        data = self._extract_json(self.chat(prompts.RESUME_DIG_SYSTEM, user, temperature=0.3))
        if not isinstance(data, list):
            raise ValueError("漏洞挖掘输出不是数组")
        return data[:3]

    def diagnose_resume(self, resume: Dict[str, Any], target_position: str) -> Dict[str, Any]:
        """简历体检：真实 LLM 优先，任何异常回落到确定性启发式（app.services.diagnosis）。"""
        if not self.mock:
            try:
                user = prompts.RESUME_DIAGNOSE_USER_TMPL.format(
                    target_position=target_position or "未指定",
                    resume_json=json.dumps(resume, ensure_ascii=False)[:6000],
                )
                data = self._extract_json(self.chat(prompts.RESUME_DIAGNOSE_SYSTEM, user, temperature=0.2))
                scores = data.get("scores", {})
                from app.services.diagnosis import DIM_LABELS

                clean = {k: round(max(0.0, min(10.0, float(scores.get(k, 0)))), 1)
                         for k in DIM_LABELS}
                return {
                    "scores": clean,
                    "overall": round(sum(clean.values()) / len(clean) * 10),
                    "comment": str(data.get("comment", ""))[:200],
                    "suggestions": list(data.get("suggestions", []))[:5],
                    "mode": "llm",
                }
            except Exception:  # noqa: BLE001 - LLM 失败不阻断上传
                pass
        from app.services import diagnosis as diag

        result = diag.diagnose(resume, target_position)
        result["mode"] = "mock" if self.mock else "heuristic"
        return result

    # ------------------------------------------------------------------
    # 面试话术
    # ------------------------------------------------------------------
    def intro_message(self, resume: Dict[str, Any], weaknesses: List[Dict[str, Any]],
                      target_position: str, emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            msg = mock_llm.intro_message(resume, weaknesses, target_position)
            mock_llm.emit_text(msg, emit)
            return msg
        return self.chat(
            prompts.INTERVIEWER_SYSTEM.format(target_position=target_position or "技术岗"),
            "面试刚开始，请做开场：说明面试流程（项目深挖、技术基础、压力测试三段），"
            f"并提到你已在简历中标记了 {len(weaknesses)} 个待深挖的点，最后让候选人做一个简单自我介绍。",
            emit=emit,
        )

    def probe_question(self, weakness: Dict[str, Any], target_position: str,
                       emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            msg = mock_llm.probe_question(weakness)
            mock_llm.emit_text(msg, emit)
            return msg
        user = prompts.PROBE_QUESTION_TMPL.format(
            quote=weakness.get("quote", ""), reason=weakness.get("reason", ""),
            probe_angle=weakness.get("probe_angle", ""),
        )
        return self.chat(prompts.INTERVIEWER_SYSTEM.format(target_position=target_position or "技术岗"),
                         user, emit=emit)

    def followup_question(self, question: str, answer: str, depth: int, reasons: List[str],
                          target_position: str, emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            msg = mock_llm.followup_question(question, answer, depth, settings.max_followup_depth, reasons)
            mock_llm.emit_text(msg, emit)
            return msg
        user = prompts.FOLLOWUP_TMPL.format(
            question=question, answer=answer[:600],
            reasons="；".join(reasons) or "细节不足", depth=depth, max_depth=settings.max_followup_depth,
        )
        return self.chat(prompts.INTERVIEWER_SYSTEM.format(target_position=target_position or "技术岗"),
                         user, emit=emit)

    def drill_question(self, entry: Dict[str, Any], target_position: str,
                       emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            msg = mock_llm.drill_question(entry)
            mock_llm.emit_text(msg, emit)
            return msg
        source = f"（来源：{entry.get('company', '大厂')}面经，分类：{entry.get('category', '基础')}）" if entry.get("id") else ""
        return self.chat(
            prompts.INTERVIEWER_SYSTEM.format(target_position=target_position or "技术岗"),
            f"请基于下面这道大厂真题向候选人提问，可以稍作口语化改写但不要降低难度，一次只问一题。\n题目：{entry['question']}\n{source}",
            emit=emit,
        )

    def stress_question(self, quote: str, scenario: str, target_position: str,
                        emit: Optional[Callable[[str], None]] = None) -> str:
        if self.mock:
            msg = mock_llm.stress_question(quote, scenario)
            mock_llm.emit_text(msg, emit)
            return msg
        return self.chat(
            prompts.INTERVIEWER_SYSTEM.format(target_position=target_position or "技术岗"),
            prompts.STRESS_TMPL.format(quote=quote, scenario=scenario), emit=emit,
        )

    # ------------------------------------------------------------------
    # JD 对比诊断
    # ------------------------------------------------------------------
    def jd_match(self, resume: Dict[str, Any], jd_text: str, target_position: str) -> Dict[str, Any]:
        """真实 LLM 优先，异常回落确定性匹配（app.services.jd_matcher）。"""
        if not self.mock:
            try:
                user = prompts.JD_MATCH_USER_TMPL.format(
                    target_position=target_position or "未指定",
                    jd_text=(jd_text or "")[:6000],
                    resume_json=json.dumps(resume, ensure_ascii=False)[:5000],
                )
                data = self._extract_json(self.chat(prompts.JD_MATCH_SYSTEM, user, temperature=0.2))
                matched = [str(k) for k in data.get("matched", [])][:25]
                missing = [str(k) for k in data.get("missing", [])][:25]
                return {
                    "match_score": int(max(0, min(100, data.get("match_score", 0)))),
                    "keywords_total": len(data.get("keywords", matched + missing)),
                    "matched": matched,
                    "missing": missing,
                    "suggestions": list(data.get("suggestions", []))[:6],
                    "summary": str(data.get("summary", ""))[:300],
                    "mode": "llm",
                }
            except Exception:  # noqa: BLE001
                pass
        from app.services import jd_matcher

        result = jd_matcher.match_jd(jd_text, resume, target_position)
        result["mode"] = "mock" if self.mock else "heuristic"
        return result

    # ------------------------------------------------------------------
    # LLM-as-a-Judge
    # ------------------------------------------------------------------
    def judge(self, transcript: List[Dict[str, Any]], stats: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock:
            return mock_llm.judge(transcript, stats)
        user = prompts.JUDGE_USER_TMPL.format(
            target_position=stats.get("target_position") or "未指定",
            probe_rounds=stats.get("probe_rounds", 0), drill_rounds=stats.get("drill_rounds", 0),
            stress_rounds=stats.get("stress_rounds", 0),
            transcript=json.dumps(transcript, ensure_ascii=False)[:12000],
        )
        data = self._extract_json(self.chat(prompts.JUDGE_SYSTEM, user, temperature=0.2))
        if not isinstance(data, dict) or "scores" not in data:
            raise ValueError("Judge 输出格式异常")
        return data
