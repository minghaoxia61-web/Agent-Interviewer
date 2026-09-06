"""登录令牌：GitHub OAuth 登录后签发的 HMAC 访客身份（30 天有效）。

- 签名密钥：优先使用 ACCESS_TOKEN；未设置时生成随机密钥存入 meta 表；
- 令牌格式：{owner}:{过期时间戳}:{HMAC-SHA256 签名}——无状态校验，无服务端会话。
"""
import hashlib
import hmac
import secrets
import time
from typing import Optional

from app.core.config import settings
from app.storage import db

_LOGIN_SECRET_KEY = "login_secret"


def _secret() -> str:
    if settings.access_token.strip():
        return settings.access_token
    rows = db.query("SELECT value FROM meta WHERE key = ?", (_LOGIN_SECRET_KEY,))
    if rows:
        return rows[0]["value"]
    s = secrets.token_urlsafe(32)
    db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)", (_LOGIN_SECRET_KEY, s))
    return s


def issue_login_token(owner: str, days: int = 30) -> str:
    exp = int(time.time()) + days * 86400
    payload = f"{owner}:{exp}".encode("utf-8")
    sig = hmac.new(_secret().encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{owner}:{exp}:{sig}"


def verify_login_token(token: str) -> Optional[str]:
    """校验登录令牌，有效则返回 owner，无效/过期返回 None。"""
    try:
        owner, exp_str, sig = token.strip().split(":", 2)
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return None
    if exp < time.time() or not owner:
        return None
    payload = f"{owner}:{exp}".encode("utf-8")
    expected = hmac.new(_secret().encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return owner if hmac.compare_digest(expected, sig) else None
