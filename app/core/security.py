"""轻量安全护栏：访问令牌 + 每日调用限额。

设计目标：demo 后端暴露公网时，防止 LLM 费用被刷爆。
- 未配置 ACCESS_TOKEN 时，本地开发零摩擦（只限流）；
- 配置后，所有 /api/* 请求需携带 X-API-Token 头（或 ?token= 查询参数），WS 同理；
- 限额按客户端 IP 每自然日计数，超过返回 429。
"""
from collections import defaultdict
from datetime import date
from typing import Dict, Tuple

from fastapi import HTTPException, Request, WebSocket

from app.core.config import settings


class DailyLimiter:
    """内存态按日计数器（进程重启即清零，demo 场景足够）。"""

    def __init__(self) -> None:
        self._hits: Dict[str, Tuple[str, int]] = {}

    def hit(self, key: str, limit: int) -> bool:
        today = date.today().isoformat()
        day, count = self._hits.get(key, (today, 0))
        if day != today:
            day, count = today, 0
        count += 1
        self._hits[key] = (day, count)
        return count <= limit


limiter = DailyLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _token_ok(provided: str) -> bool:
    if not settings.access_token:
        return True
    return bool(provided) and provided == settings.access_token


async def guard_http(request: Request) -> None:
    """HTTP 路由依赖：令牌校验 + 每日限额。"""
    provided = request.headers.get("x-api-token") or request.query_params.get("token", "")
    if not _token_ok(provided):
        raise HTTPException(status_code=401, detail="需要访问令牌（X-API-Token）")
    if not limiter.hit(f"api:{client_ip(request)}", settings.rate_limit_daily):
        raise HTTPException(status_code=429, detail="今日调用已达上限，请明天再试")


def guard_ws(websocket: WebSocket) -> bool:
    """WebSocket 握手校验。失败时由调用方 accept 后以 4401 关闭。"""
    provided = websocket.query_params.get("token", "")
    return _token_ok(provided)
