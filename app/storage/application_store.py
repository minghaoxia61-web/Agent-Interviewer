"""求职投递记录存储（JSON 文件持久化 + 线程安全 CRUD）。"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

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
        self._path: Path = settings.data_dir / "applications.json"
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, items: List[Dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def list(self, owner: str = "") -> List[Dict[str, Any]]:
        with self._lock:
            items = self._load()
        items = [i for i in items if i.get("owner", "anonymous") == owner]
        items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return items

    def create(self, owner: str, company: str, position: str, status: str = "wishlist",
               salary: str = "", link: str = "", notes: str = "") -> Dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        item = {
            "id": uuid.uuid4().hex[:10],
            "owner": owner,
            "company": company.strip(),
            "position": position.strip(),
            "status": status if status in STATUSES else "wishlist",
            "salary": salary.strip(),
            "link": link.strip(),
            "notes": notes.strip(),
            "created_at": now,
            "updated_at": now,
            "timeline": [{"status": status if status in STATUSES else "wishlist", "ts": now}],
        }
        with self._lock:
            items = self._load()
            items.append(item)
            self._save(items)
        return item

    def update(self, app_id: str, patch: Dict[str, Any],
               owner: str = "") -> Optional[Dict[str, Any]]:
        with self._lock:
            items = self._load()
            for it in items:
                if it["id"] != app_id or it.get("owner", "anonymous") != owner:
                    continue
                new_status = patch.get("status")
                if new_status and new_status in STATUSES and new_status != it["status"]:
                    it["status"] = new_status
                    it.setdefault("timeline", []).append({"status": new_status,
                                                          "ts": datetime.now().isoformat(timespec="seconds")})
                for f in ("company", "position", "salary", "link", "notes"):
                    if f in patch and patch[f] is not None:
                        it[f] = str(patch[f]).strip()
                it["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self._save(items)
                return it
        return None

    def delete(self, app_id: str, owner: str = "") -> bool:
        with self._lock:
            items = self._load()
            rest = [it for it in items if not (it["id"] == app_id and it.get("owner", "anonymous") == owner)]
            if len(rest) == len(items):
                return False
            self._save(rest)
        return True


APPLICATIONS = ApplicationStore()
