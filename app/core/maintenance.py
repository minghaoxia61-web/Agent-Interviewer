"""数据保留策略：按天清理过期的 Trace / 报告 / 已完成会话及其 checkpoint。

- RETENTION_DAYS=30（默认），设 0 表示永久保留；
- 投递记录属于用户主动维护的数据，不参与自动清理；
- 在应用启动时执行一次，也可通过 POST /api/workbench/maintenance 手动触发。
"""
from datetime import datetime, timedelta
from typing import Dict

from app.core.config import settings
from app.storage import db


def sweep_expired() -> Dict[str, int]:
    if settings.retention_days <= 0:
        return {"skipped": 1}
    cutoff = datetime.now() - timedelta(days=settings.retention_days)
    cutoff_iso = cutoff.isoformat(timespec="seconds")
    cutoff_ts = cutoff.timestamp()
    stats = {"traces": 0, "reports": 0, "uploads": 0, "sessions": 0, "checkpoints": 0}

    # 1) 过期文件：trace / report / 原始简历
    buckets = ((settings.traces_dir, "traces"), (settings.reports_dir, "reports"),
               (settings.uploads_dir, "uploads"))
    for d, key in buckets:
        if not d.exists():
            continue
        for p in d.glob("*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff_ts:
                    p.unlink()
                    stats[key] += 1
            except OSError:
                continue

    # 2) 已完成且过期的会话（SQLite），连带清理其 LangGraph checkpoint
    try:
        rows = db.query(
            "SELECT id FROM sessions WHERE finished = 1 AND created_at < ?", (cutoff_iso,))
        for r in rows:
            tid = f"interview-{r['id']}"
            try:
                db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (tid,))
                db.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (tid,))
                db.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (tid,))
                stats["checkpoints"] += 1
            except Exception:  # noqa: BLE001 - 未启用 checkpointer 时表不存在
                pass
            db.execute("DELETE FROM sessions WHERE id = ?", (r["id"],))
            stats["sessions"] += 1
    except Exception:  # noqa: BLE001 - 数据库异常不阻塞启动
        pass
    return stats
