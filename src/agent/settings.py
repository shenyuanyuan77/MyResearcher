"""
统一配置中心（研途智探AI 网页版）。

所有可变配置从环境变量读取。通过 `from agent.settings import settings` 使用。
精简自采购助手：去 Mongo/Sandbox，默认 SQLite checkpoint。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env", override=False)
load_dotenv(override=False)


def _app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def _is_prod_env() -> bool:
    return _app_env() in {"prod", "production"}


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bool_prod_aware(name: str, *, default_dev: bool, default_prod: bool) -> bool:
    if os.getenv(name) is None:
        return default_prod if _is_prod_env() else default_dev
    return _bool(name, default_dev)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """应用全局配置。"""

    # ---- LLM ----
    deepseek_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY")
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
    )
    zhipu_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ZHIPU_API_KEY"))
    zhipu_base_url: str = field(
        default_factory=lambda: os.getenv(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
        )
    )
    main_model: str = field(
        default_factory=lambda: os.getenv("MAIN_MODEL", "deepseek-v4-pro")
    )
    summary_model: str = field(
        default_factory=lambda: os.getenv("SUMMARY_MODEL", "deepseek-v4-flash")
    )

    # ---- 学术 MCP ----
    mcp_academic_url: str = field(
        default_factory=lambda: os.getenv(
            "MCP_ACADEMIC_URL", "http://127.0.0.1:7001/mcp"
        )
    )
    mcp_api_key: Optional[str] = field(default_factory=lambda: os.getenv("MCP_API_KEY") or None)
    mcp_port: int = field(default_factory=lambda: _int("MCP_PORT", 7001))

    # ---- Auth ----
    app_env: str = field(default_factory=_app_env)
    auth_enabled: bool = field(default_factory=lambda: _bool("AUTH_ENABLED", True))
    jwt_secret: str = field(
        default_factory=lambda: os.getenv(
            "JWT_SECRET", "change-me-yanjiu-research-quest-2026"
        )
    )
    jwt_expire_hours: int = field(default_factory=lambda: _int("JWT_EXPIRE_HOURS", 24))
    # 生产默认 fail（弱配置拒启）；dev 默认 warn。可被 FAIL_ON_INSECURE_CONFIG 覆盖。
    fail_on_insecure_config: bool = field(
        default_factory=lambda: _bool_prod_aware(
            "FAIL_ON_INSECURE_CONFIG", default_dev=False, default_prod=True
        )
    )
    default_user_id: str = field(
        default_factory=lambda: os.getenv("DEFAULT_USER_ID", "yanjiu")
    )
    default_username: str = field(
        default_factory=lambda: os.getenv("DEFAULT_USERNAME", "yanjiu")
    )

    # ---- 容错 / 运行时 ----
    allow_degraded_start: bool = field(
        default_factory=lambda: _bool("ALLOW_DEGRADED_START", True)
    )
    require_mcp: bool = field(default_factory=lambda: _bool("REQUIRE_MCP", False))
    cors_origins: str = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
        )
    )
    audit_log_enabled: bool = field(default_factory=lambda: _bool("AUDIT_LOG_ENABLED", True))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # ---- 限流 / 安全头 ----
    rate_limit_enabled: bool = field(default_factory=lambda: _bool("RATE_LIMIT_ENABLED", True))
    rate_limit_window_sec: int = field(
        default_factory=lambda: _int("RATE_LIMIT_WINDOW_SEC", 60)
    )
    rate_limit_max_requests: int = field(
        default_factory=lambda: _int("RATE_LIMIT_MAX_REQUESTS", 180)
    )
    login_rate_limit_max: int = field(default_factory=lambda: _int("LOGIN_RATE_LIMIT_MAX", 10))
    security_headers_enabled: bool = field(
        default_factory=lambda: _bool("SECURITY_HEADERS_ENABLED", True)
    )

    # ---- 端口 ----
    backend_port: int = field(default_factory=lambda: _int("BACKEND_PORT", 8000))
    frontend_port: int = field(default_factory=lambda: _int("FRONTEND_PORT", 3001))
    api_title: str = field(
        default_factory=lambda: os.getenv("API_TITLE", "研途智探AI 科研导师 API")
    )
    api_version: str = field(default_factory=lambda: os.getenv("API_VERSION", "1.0.0"))

    # ---- AUTH_USERS（JSON 字符串）----
    auth_users_raw: str = field(
        default_factory=lambda: os.getenv(
            "AUTH_USERS",
            '[{"user_id":"yanjiu","username":"yanjiu","password":"yanjiu123","roles":["admin"]}]',
        )
    )

    # ---------- 方法 ----------
    def is_production(self) -> bool:
        return _is_prod_env()

    def auth_users(self) -> List[Dict[str, Any]]:
        try:
            users = json.loads(self.auth_users_raw)
            if isinstance(users, list):
                return users
        except Exception:
            pass
        return [
            {
                "user_id": "yanjiu",
                "username": "yanjiu",
                "password": "yanjiu123",
                "roles": ["admin"],
            }
        ]

    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "app_env": self.app_env,
            "auth_enabled": self.auth_enabled,
            "main_model": self.main_model,
            "summary_model": self.summary_model,
            "backend_port": self.backend_port,
            "frontend_port": self.frontend_port,
            "mcp_academic_url": self.mcp_academic_url,
        }

    def validate_startup(self) -> None:
        """启动安全校验。

        生产环境（APP_ENV=prod/production）：弱配置默认拒启（fail_on_insecure_config 默认 True）。
        开发环境：跳过校验，方便用明文密码快速启动。
        """
        if not _is_prod_env():
            return
        problems: List[str] = []
        # JWT secret：禁止默认值，长度 ≥ 32 字节（HS256 安全基线）
        if self.jwt_secret.startswith("change-me") or len(self.jwt_secret) < 32:
            problems.append(
                "JWT_SECRET 过弱（生产需 ≥32 字节且非 change-me 默认值）。"
                "生成：python -c \"import secrets;print(secrets.token_urlsafe(48))\""
            )
        # 生产禁止关闭认证
        if not self.auth_enabled:
            problems.append("AUTH_ENABLED=false 在生产环境被禁止（任何人可匿名访问）")
        # 密码必须 bcrypt 哈希（拒明文 / sha256）
        for u in self.auth_users():
            pwd = u.get("password", "")
            if pwd and not pwd.startswith("bcrypt$") and not pwd.startswith("$2"):
                problems.append(
                    f"用户 {u.get('username')} 密码非 bcrypt（生产禁止明文/sha256）。"
                    "生成：python -c \"import bcrypt;print('bcrypt$'+bcrypt.hashpw(b'密码',bcrypt.gensalt()).decode())\""
                )
        if problems:
            msg = "生产配置校验失败：\n  - " + "\n  - ".join(problems)
            if self.fail_on_insecure_config:
                raise RuntimeError(msg)
            print(f"[WARN] {msg}")


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings()


settings = _settings()
