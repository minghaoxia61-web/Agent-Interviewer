"""求职投递记录存储（SQLite 持久化 + 线程安全 CRUD，按访客隔离）。"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.storage import db

STATUSES = {
    "wishlist": "想投",
    "applied": "已投递",
    "written_test": "笔试",
    "interview": "面试",
    "offer": "Offer",
    "rejected": "已挂",
}


class ApplicationStore:
    def __init__(self) -> None:
        self._migrate_legacy_json()

    def _migrate_legacy_json(self) -> None:
        """旧版 applications.json 一次性导入 SQLite。"""
        legacy = settings.data_dir / "applications.json"
        if not legacy.exists():
            return
        moved = 0
        try:
            import json as _json
            items = _json.loads(legacy.read_text(encoding="utf-8"))
            for it in items if isinstance(items, list) else []:
                if not it.get("id"):
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO applications "
                    "(id, owner, company, position, status, salary, link, notes, "
                    " created_at, updated_at, timeline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (it["id"], it.get("owner", "anonymous"), it.get("company", ""),
                     it.get("position", ""), it.get("status", "wishlist"),
                     it.get("salary", ""), it.get("link", ""), it.get("notes", ""),
                     it.get("created_at", ""), it.get("updated_at", ""),
                     db.dumps(it.get("timeline", []))),
                )
                moved += 1
            legacy.rename(legacy.with_suffix(".json.imported"))
        except Exception:  # noqa: BLE001 - 导入失败不阻塞启动
            pass
        if moved:
            print(f"[RAI] 已从 applications.json 导入 {moved} 条历史投递记录到 SQLite")

    @staticmethod
    def _to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "owner": row.get("owner", ""),
            "company": row.get("company", ""),
            "position": row.get("position", ""),
            "status": row.get("status", "wishlist"),
            "salary": row.get("salary", ""),
            "link": row.get("link", ""),
            "notes": row.get("notes", ""),
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
            "timeline": db.loads(row.get("timeline"), []),
        }

    def reassign_owner(self, old: str, new: str) -> int:
        db.execute("UPDATE applications SET owner = ? WHERE owner = ?", (new, old))
        return 1

    def list(self, owner: str = "") -> List[Dict[str, Any]]:
        rows = db.query("SELECT * FROM applications WHERE owner = ? ORDER BY updated_at DESC",
                        (owner,))
        return [self._to_item(r) for r in rows]

    def create(self, owner: str, company: str, position: str, status: str = "wishlist",
               salary: str = "", link: str = "", notes: str = "") -> Dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        item_id = uuid.uuid4().hex[:10]
        status = status if status in STATUSES else "wishlist"
        db.execute(
            "INSERT INTO applications (id, owner, company, position, status, salary, link, "
            "notes, created_at, updated_at, timeline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, owner, company.strip(), position.strip(), status, salary.strip(),
             link.strip(), notes.strip(), now, now, db.dumps([{"status": status, "ts": now}])),
        )
        return {"id": item_id, "owner": owner, "company": company.strip(),
                "position": position.strip(), "status": status, "salary": salary.strip(),
                "link": link.strip(), "notes": notes.strip(),
                "created_at": now, "updated_at": now,
                "timeline": [{"status": status, "ts": now}]}

    def update(self, app_id: str, patch: Dict[str, Any],
               owner: str = "") -> Optional[Dict[str, Any]]:
        rows = db.query("SELECT * FROM applications WHERE id = ? AND owner = ?", (app_id, owner))
        if not rows:
            return None
        row = rows[0]
        timeline = db.loads(row.get("timeline"), [])
        new_status = patch.get("status")
        if new_status and new_status in STATUSES and new_status != row["status"]:
            timeline.append({"status": new_status, "ts": datetime.now().isoformat(timespec="seconds")})
        fields = {"company": row["company"], "position": row["position"],
                  "salary": row["salary"], "link": row["link"], "notes": row["notes"],
                  "status": row["status"]}
        for f in ("company", "position", "salary", "link", "notes"):
            if f in patch and patch[f] is not None:
                fields[f] = str(patch[f]).strip()
        if new_status and new_status in STATUSES:
            fields["status"] = new_status
        db.execute(
            "UPDATE applications SET company=?, position=?, status=?, salary=?, link=?, "
            "notes=?, updated_at=?, timeline=? WHERE id=?",
            (fields["company"], fields["position"], fields["status"], fields["salary"],
             fields["link"], fields["notes"],
             datetime.now().isoformat(timespec="seconds"), db.dumps(timeline), app_id),
        )
        return self.get_one(app_id, owner)

    def delete(self, app_id: str, owner: str = "") -> bool:
        cur = db.execute("DELETE FROM applications WHERE id = ? AND owner = ?", (app_id, owner))
        return cur.rowcount > 0

    def get_one(self, app_id: str, owner: str = "") -> Optional[Dict[str, Any]]:
        rows = db.query("SELECT * FROM applications WHERE id = ? AND owner = ?", (app_id, owner))
        return self._to_item(rows[0]) if rows else None


APPLICATIONS = ApplicationStore()
