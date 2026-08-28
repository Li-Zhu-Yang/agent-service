"""依赖注入：数据库会话 / 当前用户 / 客户端 IP。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.exceptions import AuthError, ForbiddenError
from models.user import User
from services.auth import decode_token

# 会话依赖（必须用 Depends 包装，否则 FastAPI 误判为响应字段）
DbSession = Annotated[Session, Depends(get_db)]


def get_client_ip(request: Request) -> str:
    """获取客户端 IP（兼容反代 X-Forwarded-For）。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    """从 Bearer Token 解析当前用户。"""
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
