"""就业工作台 API：仪表盘 / 会话档案 / 真题题库 / LLM 观测。"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.security import visitor_id
from app.services.orchestrator import ORCHESTRATOR
from app.storage import db

router = APIRouter(prefix="/api/workbench", tags=["workbench"])


def _load_sessions(owner: str) -> List[Dict[str, Any]]:
    """读取当前访客的会话（含进行中），按创建时间倒序。"""
    rows = db.query("SELECT * FROM sessions WHERE owner = ? ORDER BY created_at DESC", (owner,))
    out: List[Dict[str, Any]] = []
    for row in rows:
        messages = db.loads(row.get("messages"), [])
        resume = db.loads(row.get("resume"), {}) or {}
        diagnosis = db.loads(row.get("diagnosis"), {}) or {}
        out.append({
            "id": row.get("id", ""),
            "created_at": row.get("created_at", ""),
            "target_position": row.get("target_position", ""),
            "finished": bool(row.get("finished")),
            "stage": row.get("stage", "intro"),
            "overall": row.get("overall") or None,
            "total_turns": sum(1 for m in messages if m.get("role") == "user"),
            "weakness_count": len(db.loads(row.get("weaknesses"), []) or []),
            "diagnosis_overall": diagnosis.get("overall"),
            "resume_name": resume.get("name", ""),
        })
    return out


@router.get("/dashboard")
def dashboard(request: Request) -> Dict[str, Any]:
    sessions = _load_sessions(visitor_id(request))
    scored = [s["overall"] for s in sessions if s.get("overall")]
    finished = [s for s in sessions if s["finished"]]
    unfinished = next((s for s in sessions if not s["finished"]), None)
    weak_total = sum(s["weakness_count"] for s in sessions)
    stats = dict(ORCHESTRATOR.llm.stats)
    stats["avg_ms"] = round(stats["total_ms"] / stats["calls"], 1) if stats["calls"] else 0
    return {
        "llm_mode": "mock" if ORCHESTRATOR.llm.mock else "real",
        "llm_model": settings.llm_model,
        "question_count": len(ORCHESTRATOR.retriever.entries),
        "session_count": len(sessions),
        "finished_count": len(finished),
        "avg_score": round(sum(scored) / len(scored), 1) if scored else None,
        "best_score": max(scored) if scored else None,
        "weakness_total": weak_total,
        "llm_stats": stats,
        "unfinished": unfinished,
        "recent": sessions[:5],
    }


@router.get("/sessions")
def list_sessions(request: Request) -> List[Dict[str, Any]]:
    return _load_sessions(visitor_id(request))


@router.get("/llm-stats")
def llm_stats() -> Dict[str, Any]:
    s = dict(ORCHESTRATOR.llm.stats)
    s["avg_ms"] = round(s["total_ms"] / s["calls"], 1) if s["calls"] else 0
    s["recent"] = list(ORCHESTRATOR.llm.recent_calls)[-12:]
    s["llm_mode"] = "mock" if ORCHESTRATOR.llm.mock else "real"
    s["llm_model"] = settings.llm_model
    return s


@router.get("/questions")
def list_questions(q: Optional[str] = None, category: Optional[str] = None,
                   company: Optional[str] = None) -> Dict[str, Any]:
    entries = [e.model_dump() for e in ORCHESTRATOR.retriever.entries]
    categories = sorted({e["category"] for e in entries})
    companies = sorted({e["company"] for e in entries})
    if q:
        needle = q.lower()
        entries = [e for e in entries
                   if needle in e["question"].lower()
                   or any(needle in k.lower() for k in e["keywords"])]
    if category:
        entries = [e for e in entries if e["category"] == category]
    if company:
        entries = [e for e in entries if e["company"] == company]
    return {"total": len(entries), "categories": categories,
            "companies": companies, "items": entries}
