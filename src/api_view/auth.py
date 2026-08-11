"""
研途智探AI · 用户鉴权：JWT + 环境变量用户表。

密码格式（verify 按前缀识别）：
  - bcrypt$<hash>  推荐生产
  - $2a$ / $2b$    bcrypt 原生串
  - sha256$<hex>   兼容旧哈希
  - 明文           仅开发；生产由 settings.validate_startup 拦截
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from agent.settings import settings
from api_view.observability import user_id_ctx

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserInfo(BaseModel):
    user_id: str
    username: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# 研途 RBAC：角色 → 权限点
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "research:read", "research:write",
        "report:export", "user:manage",
    ],
    "researcher": [
        "research:read", "research:write", "report:export",
    ],
    "student": [
        "research:read", "research:write",
    ],
    "viewer": [
        "research:read",
    ],
}


def permissions_for_roles(roles: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for role in roles:
        for perm in ROLE_PERMISSIONS.get(role, []):
            if perm not in seen:
                seen.add(perm)
                out.append(perm)
    return out


def has_permission(user: UserInfo, required: str) -> bool:
    if "admin" in (user.roles or []):
        return True
    return required in (user.permissions or [])


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(
        (settings.jwt_secret + ":" + password).encode("utf-8")
    ).hexdigest()


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return "bcrypt$" + hashed.decode("utf-8")


def _verify_bcrypt(plain: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError) as e:
        logger.warning("bcrypt 校验失败: %s", e)
        return False


def verify_password(plain: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("bcrypt$"):
        return _verify_bcrypt(plain, stored[7:])
    if stored.startswith("$2a$") or stored.startswith("$2b$") or stored.startswith("$2y$"):
        return _verify_bcrypt(plain, stored)
    if stored.startswith("sha256$"):
        return hmac.compare_digest(_legacy_sha256(plain), stored[7:])
    return hmac.compare_digest(plain, stored)


def find_user(username: str) -> Optional[Dict[str, Any]]:
    for u in settings.auth_users():
        if u.get("username") == username:
            return u
    return None


def _build_user_info(user_row: Dict[str, Any]) -> UserInfo:
    roles = list(user_row.get("roles") or ["student"])
    perms = permissions_for_roles(roles)
    for p in (user_row.get("permissions") or []):
        if p not in perms:
            perms.append(p)
    return UserInfo(
        user_id=str(user_row.get("user_id") or user_row.get("username")),
        username=str(user_row["username"]),
        roles=roles,
        permissions=perms,
    )


def create_access_token(
    user_id: str,
    username: str,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "roles": roles or [],
        "permissions": permissions or [],
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效或过期的令牌: {e}",
        ) from e


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> UserInfo:
    if not settings.auth_enabled:
        user = UserInfo(
            user_id=settings.default_user_id,
            username=settings.default_username,
            roles=["admin"],
            permissions=permissions_for_roles(["admin"]),
        )
        user_id_ctx.set(user.user_id)
        return user

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录，请先获取访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    username = payload.get("username") or user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌缺少用户标识")

    roles = payload.get("roles") or []
    if not roles:
        u = find_user(str(username))
        if u:
            roles = list(u.get("roles") or ["student"])

    user = UserInfo(
        user_id=str(user_id),
        username=str(username),
        roles=list(roles),
        permissions=payload.get("permissions") or permissions_for_roles(roles),
    )
    user_id_ctx.set(user.user_id)
    return user


def require_permission(required: str):
    async def _checker(user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if not has_permission(user, required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要 {required}（当前角色 {user.roles}）",
            )
        return user
    return _checker


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[UserInfo]:
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
