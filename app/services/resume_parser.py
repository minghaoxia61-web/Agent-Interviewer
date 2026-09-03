"""简历文本提取与结构化。"""
import re
from pathlib import Path
from typing import Tuple

from app.schemas.resume import ResumeParsed
from app.services.llm import LLMService, LLMError
from app.services import mock_llm

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber

        parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        # 清理 CID 字体无法映射的字符伪影（如示例 PDF 的项目符号）
        return re.sub(r"\(cid:\d+\)", "", text).strip()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    raise ValueError(f"不支持的文件类型: {suffix}")


def parse_resume(llm: LLMService, text: str, target_position: str) -> Tuple[ResumeParsed, str]:
    """返回 (结构化简历, 解析模式 llm|heuristic)。LLM 失败时自动降级为启发式解析。"""
    if not text:
        raise ValueError("简历内容为空，无法解析")
    mode = "llm" if not llm.mock else "heuristic"
    try:
        data = llm.parse_resume(text, target_position)
        parsed = ResumeParsed(**data)
    except (LLMError, Exception):  # noqa: B014 - 任何解析失败都降级，保证上传链路不中断
        parsed = ResumeParsed(**mock_llm.parse_resume(text, target_position))
        mode = "heuristic"
    parsed.raw_text_chars = len(text)
    return parsed, mode
