"""GitHub OAuth 登录 + 访客身份迁移。"""
import secrets
import time
from typing import Dict

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import issue_login_token, verify_login_token
from app.core.config import settings
from app.core.security import visitor_id
from app.storage.application_store import APPLICATIONS
from app.storage.session_store import STORE

router = APIRouter(prefix="/api/auth", tags=["auth"])

_states: Dict[str, float] = {}
_STATE_TTL = 600  # 授权跳转有效期 10 分钟


def _oauth_enabled() -> bool:
    return bool(settings.github_client_id and settings.github_client_secret)


class TokenExchange(BaseModel):
    code: str
    state: str
    visitor_id: str = ""


class VerifyIn(BaseModel):
    login_token: str


@router.get("/github/url")
def github_url():
    """返回 GitHub 授权跳转地址；未配置 OAuth 应用时 404（前端隐藏登录入口）。"""
    if not _oauth_enabled():
        raise HTTPException(status_code=404, detail="GitHub 登录未启用")
    state = secrets.token_urlsafe(16)
    _states[state] = time.time() + _STATE_TTL
    url = (f"https://github.com/login/oauth/authorize"
           f"?client_id={settings.github_client_id}&state={state}&scope=read:user")
    return {"url": url, "state": state}


@router.post("/github/token")
async def github_token(body: TokenExchange, request: Request):
    """用授权码换取登录令牌，并把当前访客的历史数据迁移到 GitHub 身份下。"""
    if not _oauth_enabled():
        raise HTTPException(status_code=404, detail="GitHub 登录未启用")
    issued = _states.pop(body.state, 0)
    if not issued or issued < time.time():
        raise HTTPException(status_code=422, detail="state 已过期，请重新发起登录")

    async with httpx.AsyncClient(timeout=20) as client:
        tr = await client.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": settings.github_client_id,
                  "client_secret": settings.github_client_secret,
                  "code": body.code},
            headers={"Accept": "application/json"})
        access_token = tr.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="GitHub 授权码无效或已使用")
        ur = await client.get("https://api.github.com/user",
                              headers={"Authorization": f"Bearer {access_token}"})
        user = ur.json()

    gh_id = str(user.get("id", ""))
    if not gh_id:
        raise HTTPException(status_code=401, detail="无法获取 GitHub 用户信息")

    owner = f"gh:{gh_id}"
    name = user.get("name") or user.get("login", "GitHub 用户")
    avatar = user.get("avatar_url", "")

    # 数据归属迁移：当前访客的历史会话/投递记录迁移到稳定身份下
    old = (body.visitor_id or "").strip()
    if old:
        STORE.reassign_owner(old, owner)
        APPLICATIONS.reassign_owner(old, owner)

    return {
        "owner": owner,
        "name": name,
        "avatar": avatar,
        "login_token": issue_login_token(owner),
    }


@router.post("/verify")
def verify(body: VerifyIn):
    owner = verify_login_token(body.login_token)
    if not owner:
        raise HTTPException(status_code=401, detail="登录令牌无效或已过期")
    return {"owner": owner}
