"""面试对话相关的请求/响应模型。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

STAGE_LABELS = {
    "intro": "开场确认",
    "project_probing": "项目深挖",
    "tech_drill": "技术基础",
    "stress_test": "压力测试",
    "evaluation": "生成报告",
    "end": "已结束",
}


class StartResponse(BaseModel):
    session_id: str
    assistant_message: str
    stage: str
    stage_label: str


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    session_id: str
    assistant_message: str
    stage: str
    stage_label: str
    decision: Optional[str] = None  # follow_up / advance / advance_stage / None
    decision_reasons: List[str] = []
    probe_depth: int = 0
    total_turns: int = 0
    finished: bool = False


class SessionStateResponse(BaseModel):
    session_id: str
    stage: str
    stage_label: str
    target_position: str
    total_turns: int
    probe_depth: int
    focus_idx: int
    weakness_count: int
    drill_rounds: int
    stress_rounds: int
    finished: bool
    diagnosis: Dict[str, Any] = {}
    filename: Optional[str] = None
    messages: List[Dict[str, Any]] = []
