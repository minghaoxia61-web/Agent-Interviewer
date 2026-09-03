"""评估报告相关模型。"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    comment: str = ""


class ReportResponse(BaseModel):
    session_id: str
    markdown: str
    scores: List[DimensionScore]
    overall: float
    summary: str = ""
    trace_file: Optional[str] = None
