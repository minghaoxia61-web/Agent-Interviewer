"""题库练习会话存储（SQLite，按访客隔离）。"""
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.storage import db


class PracticeStore:
    def create(self, owner: str, items: List[Dict[str, Any]]) -> str:
        pid = uuid_hex()
        db.execute(
            "INSERT INTO practice (id, owner, created_at, finished, items) VALUES (?,?,?,?,?)",
            (pid, owner, now(), 0, db.dumps(items)))
        return pid

    def get(self, pid: str, owner: str) -> Optional[Dict[str, Any]]:
        rows = db.query("SELECT * FROM practice WHERE id = ? AND owner = ?", (pid, owner))
        if not rows:
            return None
        r = rows[0]
        return {"id": r["id"], "owner": r.get("owner", ""), "created_at": r.get("created_at", ""),
                "finished": bool(r.get("finished")), "items": db.loads(r.get("items"), [])}

    def save_items(self, pid: str, owner: str, items: List[Dict[str, Any]],
                   finished: bool) -> None:
        db.execute("UPDATE practice SET items=?, finished=? WHERE id=? AND owner=?",
                   (db.dumps(items), int(finished), pid, owner))

    def list(self, owner: str) -> List[Dict[str, Any]]:
        rows = db.query("SELECT * FROM practice WHERE owner = ? ORDER BY created_at DESC", (owner,))
        out = []
        for r in rows:
            items = db.loads(r.get("items"), []) or []
            answered = [i for i in items if i.get("score") is not None]
            out.append({
                "id": r["id"], "created_at": r.get("created_at", ""),
                "finished": bool(r.get("finished")), "count": len(items),
                "answered": len(answered),
                "avg_score": round(sum(i["score"] for i in answered) / len(answered), 1)
                if answered else None,
            })
        return out


def uuid_hex() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


PRACTICES = PracticeStore()
