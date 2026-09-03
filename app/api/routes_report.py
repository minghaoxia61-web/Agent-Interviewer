"""评估报告路由。"""
from fastapi import APIRouter, HTTPException

from app.schemas.report import ReportResponse
from app.services.orchestrator import ORCHESTRATOR, SessionNotFound

router = APIRouter(tags=["report"])


@router.post("/api/interview/{session_id}/finish", response_model=ReportResponse)
def finish_interview(session_id: str):
    try:
        return ORCHESTRATOR.finish(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历") from e


@router.get("/api/report/{session_id}", response_model=ReportResponse)
def get_report(session_id: str):
    try:
        return ORCHESTRATOR.report_payload(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历") from e
