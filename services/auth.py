"""JWT 认证：签发 / 校验 / FastAPI 依赖。"""
from __future__ import annotations

import datetime as dt
from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from bootstrap.settings import settings
from core.database import get_db
from core.exceptions import AuthError, ForbiddenError
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


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("未登录")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    user = db.get(User, int(payload.get("sub", 0)))
    if user is None or not user.is_active:
        raise AuthError("用户不存在或已停用")
    return user


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != "admin":
        raise ForbiddenError("需要管理员权限")
    return current_user


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User | None:
    """聊天接口用：有合法 token 返回用户，否则 None（匿名咨询）。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_token(token)
        user = db.get(User, int(payload.get("sub", 0)))
        return user if user and user.is_active else None
    except Exception:
        return None
