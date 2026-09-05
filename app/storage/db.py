"""SQLite 持久化基础层。

设计取舍（为什么从 JSON 快照迁到 SQLite）：
- 事务写入：JSON 整文件重写在高频保存（每轮对话两条）下有撕裂风险；
- 单文件好备份，且可以按 owner/状态直接 SQL 查询；
- SQLite 的 WAL 模式 + 全局写锁对本应用的并发量绰绰有余。

复杂字段（简历/消息列表等）以 JSON TEXT 列存储——它们是整体读写的数据，
不需要关系型拆列；需要查询维度的字段（owner/status/finished）单独成列。
"""
import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from app.core.config import settings

_lock = threading.RLock()  # 可重入：execute() 持锁期间会再进入 get_conn()
_conn: Optional[sqlite3.Connection] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  target_position TEXT,
  owner TEXT,
  resume TEXT,
  weaknesses TEXT,
  diagnosis TEXT,
  analysis_status TEXT DEFAULT 'done',
  analysis_error TEXT DEFAULT '',
  jd_matches TEXT,
  messages TEXT,
  stage TEXT DEFAULT 'intro',
  focus_idx INTEGER DEFAULT 0,
  probe_depth INTEGER DEFAULT 0,
  current_question TEXT DEFAULT '',
  drill_rounds INTEGER DEFAULT 0,
  drill_asked TEXT,
  stress_rounds INTEGER DEFAULT 0,
  vagueness_log TEXT,
  finished INTEGER DEFAULT 0,
  report_md TEXT DEFAULT '',
  scores TEXT,
  overall REAL DEFAULT 0,
  summary TEXT DEFAULT '',
  trace_file TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(owner);
CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY,
  owner TEXT,
  company TEXT,
  position TEXT,
  status TEXT,
  salary TEXT DEFAULT '',
  link TEXT DEFAULT '',
  notes TEXT DEFAULT '',
  created_at TEXT,
  updated_at TEXT,
  timeline TEXT
);
CREATE INDEX IF NOT EXISTS idx_applications_owner ON applications(owner);
CREATE TABLE IF NOT EXISTS llm_cache (
  key TEXT PRIMARY KEY,
  kind TEXT,
  model TEXT,
  response TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS practice (
  id TEXT PRIMARY KEY,
  owner TEXT,
  created_at TEXT,
  finished INTEGER DEFAULT 0,
  items TEXT
);
CREATE INDEX IF NOT EXISTS idx_practice_owner ON practice(owner);
"""


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(_SCHEMA)
            # 旧库补列：CREATE IF NOT EXISTS 不会给已存在的表加新列
            _cols = {r[1] for r in _conn.execute("PRAGMA table_info(sessions)")}
            if "jd_matches" not in _cols:
                _conn.execute("ALTER TABLE sessions ADD COLUMN jd_matches TEXT")
            _conn.commit()
        return _conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """写操作（自动提交）。"""
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """读操作，返回字典行。"""
    with _lock:
        cur = get_conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def loads(s: Optional[str], default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return default
