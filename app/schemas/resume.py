"""简历与漏洞挖掘相关的数据模型。"""
from typing import List

from pydantic import BaseModel, Field


class ProjectItem(BaseModel):
    name: str = ""
    role: str = ""
    period: str = ""
    stack: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)


class ResumeParsed(BaseModel):
    name: str = ""
    target_position: str = ""
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    experiences: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    raw_text_chars: int = 0


class Weakness(BaseModel):
    """从简历中挖出的待深挖疑点。dimension 取值见 prompts.RESUME_DIG_SYSTEM。"""

    dimension: str = "vague_scope"
    quote: str = ""
    reason: str = ""
    probe_angle: str = ""
