"""会话存储 + Trace Recorder（SQLite 持久化 + 内存缓存 + JSONL 轨迹落盘）。

- 会话以行形式存入 SQLite（复杂字段 JSON TEXT 列），每轮对话原子 upsert；
- 内存缓存加速读取，SQLite 是唯一事实来源（重启后自动恢复）；
- Trace 仍为逐行 JSONL（追加型事件日志，与关系数据分离）；
- 旧版 JSON 快照（data/sessions/*.json）在启动时自动一次性导入。
"""
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.storage import db


@dataclass
class Session:
    id: str
    created_at: str
    target_position: str
    resume: Dict[str, Any]
    weaknesses: List[Dict[str, Any]]
    diagnosis: Dict[str, Any] = field(default_factory=dict)
    analysis_status: str = "done"  # processing / done / failed
    analysis_error: str = ""
    owner: str = "anonymous"  # 访客标识，用于多访客数据隔离
    messages: List[Dict[str, Any]] = field(default_factory=list)
    stage: str = "intro"
    focus_idx: int = 0
    probe_depth: int = 0
    current_question: str = ""
    drill_rounds: int = 0
    drill_asked: List[str] = field(default_factory=list)
    stress_rounds: int = 0
    vagueness_log: List[Dict[str, Any]] = field(default_factory=list)
    finished: bool = False
    report_md: str = ""
    scores: List[Dict[str, Any]] = field(default_factory=list)
    overall: float = 0.0
    summary: str = ""
    trace_file: str = ""
    # LangGraph 编译产物按会话缓存（图节点通过闭包持有本会话依赖）
    graph: Any = field(default=None, repr=False, compare=False)
    # 会话级互斥锁：同一会话的并发请求串行化，避免状态竞争
    turn_lock: Any = field(default_factory=threading.Lock, repr=False, compare=False)


class SessionStore:
    # SQLite 列映射：JSON 列整体读写，其余为标量列
    _JSON_COLS = ("resume", "weaknesses", "diagnosis", "messages",
                  "drill_asked", "vagueness_log", "scores")
    _COLS = ("id", "created_at", "target_position", "owner", "resume", "weaknesses",
             "diagnosis", "analysis_status", "analysis_error", "messages", "stage",
             "focus_idx", "probe_depth", "current_question", "drill_rounds",
             "drill_asked", "stress_rounds", "vagueness_log", "finished",
             "report_md", "scores", "overall", "summary", "trace_file")
    _UPSERT_SQL = (
        f"INSERT OR REPLACE INTO sessions ({', '.join(_COLS)}) "
        f"VALUES ({', '.join('?' for _ in _COLS)})"
    )

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        for d in (settings.traces_dir, settings.reports_dir, settings.uploads_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_json()

    # ---------- 行 <-> 对象 ----------
    def _to_row(self, sess: Session) -> tuple:
        vals = []
        for c in self._COLS:
            v = getattr(sess, c)
            if c in self._JSON_COLS:
                v = db.dumps(v)
            elif isinstance(v, bool):
                v = int(v)
            vals.append(v)
        return tuple(vals)

    def _from_row(self, row: Dict[str, Any]) -> Session:
        d = dict(row)
        for c in self._JSON_COLS:
            d[c] = db.loads(d.get(c))
        return Session(
            id=d.get("id", ""),
            created_at=d.get("created_at", ""),
            target_position=d.get("target_position", ""),
            resume=d.get("resume") or {},
            weaknesses=d.get("weaknesses") or [],
            diagnosis=d.get("diagnosis") or {},
            analysis_status=d.get("analysis_status") or "done",
            analysis_error=d.get("analysis_error") or "",
            owner=d.get("owner") or "anonymous",
            messages=d.get("messages") or [],
            stage=d.get("stage") or "intro",
            focus_idx=d.get("focus_idx") or 0,
            probe_depth=d.get("probe_depth") or 0,
            current_question=d.get("current_question") or "",
            drill_rounds=d.get("drill_rounds") or 0,
            drill_asked=d.get("drill_asked") or [],
            stress_rounds=d.get("stress_rounds") or 0,
            vagueness_log=d.get("vagueness_log") or [],
            finished=bool(d.get("finished")),
            report_md=d.get("report_md") or "",
            scores=d.get("scores") or [],
            overall=d.get("overall") or 0.0,
            summary=d.get("summary") or "",
            trace_file=d.get("trace_file") or "",
        )

    def _upsert(self, sess: Session) -> None:
        db.execute(self._UPSERT_SQL, self._to_row(sess))

    # ---------- 旧版 JSON 快照一次性导入 ----------
    def _migrate_legacy_json(self) -> None:
        legacy_dir = settings.data_dir / "sessions"
        if not legacy_dir.exists():
            return
        moved = 0
        for p in sorted(legacy_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if not data.get("id"):
                    raise ValueError("no id")
                row = []
                for c in self._COLS:
                    v = data.get(c)
                    if c in self._JSON_COLS:
                        v = db.dumps(v if v is not None else [])
                    elif isinstance(v, bool):
                        v = int(v)
                    row.append(v if v is not None else (0 if c in ("focus_idx", "probe_depth", "drill_rounds", "stress_rounds") else (0.0 if c == "overall" else "")))
                if not data.get("owner"):
                    row[self._COLS.index("owner")] = "anonymous"
                db.execute(self._UPSERT_SQL, tuple(row))
                p.rename(p.with_suffix(".json.imported"))
                moved += 1
            except Exception:  # noqa: BLE001 - 单个坏文件不阻塞启动
                continue
        if moved:
            print(f"[RAI] 已从 JSON 快照导入 {moved} 个历史会话到 SQLite")

    # ---------- 公开 API ----------
    def create(self, target_position: str, resume: Dict[str, Any],
               weaknesses: List[Dict[str, Any]],
               diagnosis: Optional[Dict[str, Any]] = None,
               analysis_status: str = "done",
               owner: str = "anonymous") -> Session:
        sid = uuid.uuid4().hex[:12]
        sess = Session(
            id=sid,
            created_at=datetime.now().isoformat(timespec="seconds"),
            target_position=target_position,
            resume=resume,
            weaknesses=weaknesses,
            diagnosis=diagnosis or {},
            analysis_status=analysis_status,
            owner=owner,
        )
        with self._lock:
            self._sessions[sid] = sess
        self._upsert(sess)
        return sess

    def get(self, sid: str) -> Optional[Session]:
        sess = self._sessions.get(sid)
        if sess is not None:
            return sess
        # 内存未命中：从 SQLite 恢复（后端重启后"会话不存在"的兜底）
        with self._lock:
            sess = self._sessions.get(sid)
            if sess is not None:
                return sess
            rows = db.query("SELECT * FROM sessions WHERE id = ?", (sid,))
            if rows:
                sess = self._from_row(rows[0])
                self._sessions[sid] = sess
        return sess

    def save(self, sess: Session) -> None:
        with self._lock:
            self._sessions[sess.id] = sess
        self._upsert(sess)

    def append_message(self, sess: Session, role: str, content: str,
                       stage: str = "", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        msg = {
            "turn": len(sess.messages) + 1,
            "role": role,
            "content": content,
            "stage": stage,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        if meta:
            msg["meta"] = meta
        sess.messages.append(msg)
        self.save(sess)
        return msg

    def append_trace(self, sess: Session, record: Dict[str, Any]) -> None:
        """Trace Recorder：每轮对话一条 JSONL，评估与报表以它为唯一事实来源。"""
        if not sess.trace_file:
            sess.trace_file = str(settings.traces_dir / f"{sess.id}.jsonl")
        record = {"ts": time.time(), "session_id": sess.id, **record}
        with open(sess.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def save_report(self, sess: Session, markdown: str) -> str:
        path = settings.reports_dir / f"{sess.id}.md"
        path.write_text(markdown, encoding="utf-8")
        scores_path = settings.reports_dir / f"{sess.id}.json"
        scores_path.write_text(
            json.dumps({
                "session_id": sess.id, "overall": sess.overall, "summary": sess.summary,
                "scores": sess.scores,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)


STORE = SessionStore()
