"""会话存储 + Trace Recorder（内存态会话 + 磁盘 JSONL 轨迹落盘）。"""
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings


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
    # 会话快照里持久化的字段（graph 为运行时对象，不落盘）
    _PERSISTED = ("id", "created_at", "target_position", "resume", "weaknesses",
                  "diagnosis", "analysis_status", "analysis_error", "owner", "messages",
                  "stage", "focus_idx", "probe_depth",
                  "current_question", "drill_rounds", "drill_asked", "stress_rounds",
                  "vagueness_log", "finished", "report_md", "scores", "overall",
                  "summary", "trace_file")

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        for d in (settings.traces_dir, settings.reports_dir, settings.uploads_dir,
                  settings.data_dir / "sessions"):
            d.mkdir(parents=True, exist_ok=True)

    def _snap_path(self, sid: str) -> Path:
        return settings.data_dir / "sessions" / f"{sid}.json"

    def _save(self, sess: Session) -> None:
        data = {f: getattr(sess, f) for f in self._PERSISTED}
        try:
            self._snap_path(sess.id).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # 落盘失败不影响内存态面试

    def _load(self, sid: str) -> Optional[Session]:
        p = self._snap_path(sid)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        defaults = {"messages": [], "weaknesses": [], "resume": {},
                    "drill_asked": [], "vagueness_log": [], "scores": []}
        sess = Session(
            id=data["id"],
            created_at=data.get("created_at", ""),
            target_position=data.get("target_position", ""),
            resume=data.get("resume") or {},
            weaknesses=data.get("weaknesses") or [],
        )
        for f in self._PERSISTED:
            if f in ("id", "created_at", "target_position", "resume", "weaknesses"):
                continue
            setattr(sess, f, data.get(f, defaults.get(f, "" if f != "finished" else False)))
        return sess

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
        self._save(sess)
        return sess

    def get(self, sid: str) -> Optional[Session]:
        sess = self._sessions.get(sid)
        if sess is not None:
            return sess
        # 内存未命中：从磁盘快照恢复（后端重启后"会话不存在"的兜底）
        with self._lock:
            sess = self._sessions.get(sid)
            if sess is not None:
                return sess
            sess = self._load(sid)
            if sess is not None:
                self._sessions[sid] = sess
        return sess

    def save(self, sess: Session) -> None:
        with self._lock:
            self._sessions[sess.id] = sess
        self._save(sess)

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
        self._save(sess)
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
