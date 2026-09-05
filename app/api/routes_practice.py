"""题库练习模式路由：选一组真题 → 逐题作答 → LLM 教练批改 + 参考要点。"""
import random
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.security import ensure_owner, visitor_id
from app.services.orchestrator import ORCHESTRATOR
from app.storage.practice_store import PRACTICES

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _owned_practice(pid: str, request: Request) -> Dict[str, Any]:
    prac = PRACTICES.get(pid, visitor_id(request))
    if prac is None:
        raise HTTPException(status_code=404, detail="练习会话不存在")
    return prac


class PracticeStart(BaseModel):
    category: Optional[str] = None
    company: Optional[str] = None
    count: int = 5


class PracticeAnswer(BaseModel):
    answer: str


@router.post("/start")
def start_practice(body: PracticeStart, request: Request):
    count = max(1, min(10, body.count or 5))
    entries = [e.model_dump() for e in ORCHESTRATOR.retriever.entries]
    if body.category:
        entries = [e for e in entries if e["category"] == body.category]
    if body.company:
        entries = [e for e in entries if e["company"] == body.company]
    if not entries:
        raise HTTPException(status_code=422, detail="该筛选条件下没有可用题目")
    picked = random.sample(entries, min(count, len(entries)))
    items = [{"qid": e["id"], "question": e["question"],
              "answer": None, "score": None, "feedback": None} for e in picked]
    pid = PRACTICES.create(visitor_id(request), items)
    return {"practice_id": pid, "index": 0, "total": len(items),
            "question": items[0]["question"]}


@router.post("/{pid}/answer")
def submit_answer(pid: str, body: PracticeAnswer, request: Request):
    prac = _owned_practice(pid, request)
    items = prac["items"]
    idx = next((i for i, it in enumerate(items) if it.get("answer") is None), None)
    if idx is None:
        raise HTTPException(status_code=409, detail="本组练习已全部作答")
    if not body.answer.strip():
        raise HTTPException(status_code=422, detail="回答不能为空")

    question = items[idx]["question"]
    result = ORCHESTRATOR.llm.practice_eval(question, body.answer.strip())
    feedback = {"strengths": result["strengths"], "gaps": result["gaps"],
                "reference": result["reference"]}
    items[idx].update(answer=body.answer.strip(), score=result["score"],
                      feedback=feedback, eval_mode=result["mode"])
    finished = all(it.get("answer") is not None for it in items)
    PRACTICES.save_items(pid, visitor_id(request), items, finished)

    nxt = items[idx + 1] if not finished and idx + 1 < len(items) else None
    return {
        "score": result["score"], "feedback": feedback, "eval_mode": result["mode"],
        "index": idx + 1, "total": len(items), "finished": finished,
        "next_question": nxt["question"] if nxt else None,
    }


@router.get("/history")
def practice_history(request: Request):
    return PRACTICES.list(visitor_id(request))


@router.get("/{pid}")
def get_practice(pid: str, request: Request):
    return _owned_practice(pid, request)
