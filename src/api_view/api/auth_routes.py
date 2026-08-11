"""研途智探AI · 认证 API。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent.settings import settings
from api_view.auth import (
    LoginRequest,
    TokenResponse,
    UserInfo,
    _build_user_info,
    create_access_token,
    find_user,
    get_current_user,
    verify_password,
)
from api_view.observability import write_audit

router = APIRouter(prefix="/auth", tags=["认证"])

_login_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit_login(ip: str) -> None:
    now = time.time()
    window = settings.rate_limit_window_sec
    max_attempts = settings.login_rate_limit_max
    q = _login_hits[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": str(window)},
        )
    q.append(now)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    ip = _client_ip(request)
    _rate_limit_login(ip)

    user = find_user(body.username)
    if not user or not verify_password(body.password, user.get("password", "")):
        write_audit(
            "auth.login",
            user_id=body.username,
            success=False,
            detail={"reason": "bad_credentials", "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    user_id = user.get("user_id") or user["username"]
    user_info = _build_user_info(user)
    token = create_access_token(
        user_id=user_info.user_id,
        username=user_info.username,
        roles=user_info.roles,
        permissions=user_info.permissions,
    )
    write_audit(
        "auth.login",
        user_id=user_id,
        success=True,
        detail={"ip": ip, "roles": user_info.roles},
    )
    return TokenResponse(access_token=token, user=user_info)


@router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(get_current_user)):
    return user
