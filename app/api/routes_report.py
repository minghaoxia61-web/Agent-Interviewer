"""评估报告路由 + 追问复盘数据。"""
from fastapi import APIRouter, HTTPException, Request

from app.core.security import ensure_owner
from app.schemas.report import ReportResponse
from app.services.orchestrator import ORCHESTRATOR, SessionNotFound
from app.storage.session_store import STORE

router = APIRouter(tags=["report"])


def _owned_session(session_id: str, request: Request):
    sess = STORE.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    ensure_owner(sess.owner, request)
    return sess


@router.post("/api/interview/{session_id}/finish", response_model=ReportResponse)
def finish_interview(session_id: str, request: Request):
    _owned_session(session_id, request)
    try:
        return ORCHESTRATOR.finish(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历") from e


@router.get("/api/report/{session_id}", response_model=ReportResponse)
def get_report(session_id: str, request: Request):
    _owned_session(session_id, request)
    try:
        return ORCHESTRATOR.report_payload(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历") from e


@router.get("/api/interview/{session_id}/review")
def get_review(session_id: str, request: Request):
    """追问复盘：逐轮 (问题, 回答, 决策, 触发原因) 轨迹 + 统计，供追问树可视化。"""
    sess = _owned_session(session_id, request)
    chains = []
    msgs = sess.messages
    for i, m in enumerate(msgs):
        if m["role"] == "assistant" and i + 1 < len(msgs) and msgs[i + 1]["role"] == "user":
            meta = m.get("meta") or {}
            chains.append({
                "turn": msgs[i + 1]["turn"] - 1,
                "stage": m.get("stage", ""),
                "question": m["content"],
                "answer": msgs[i + 1]["content"],
                "decision": meta.get("decision"),
                "reasons": meta.get("reasons", []),
                "depth": meta.get("probe_depth", 0),
            })
    follow_ups = [c for c in chains if c["decision"] == "follow_up"]
    stats = {
        "turns": len(chains),
        "follow_ups": len(follow_ups),
        "max_depth": max((c["depth"] for c in chains), default=0),
    }
    return {
        "session_id": sess.id,
        "target_position": sess.target_position,
        "chains": chains,
        "stats": stats,
    }
