"""JWT 认证（纯逻辑层）：签发 / 校验 Token。

FastAPI 依赖（get_current_user / require_admin / get_optional_user）
统一收敛在 api/dependencies.py。
"""
from __future__ import annotations

import datetime as dt

import jwt

from bootstrap.settings import settings
from core.exceptions import AuthError
from models.user import User


def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.jwt_expire_minutes),
        "iat": dt.datetime.now(dt.timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise AuthError("无效的登录凭证")
