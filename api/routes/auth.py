"""认证接口：登录 / 当前用户。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request

from api.dependencies import DbSession, get_client_ip
from core.exceptions import AuthError
from schemas.admin import LoginRequest
from schemas.common import Envelope
from system.auth import create_access_token, get_current_user
from system.audit import write_audit
from system.user import get_user_by_username

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Envelope)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> Envelope:
    user = get_user_by_username(db, payload.username)
    if user is None or not user.check_password(payload.password):
        raise AuthError("用户名或密码错误")
    if not user.is_active:
        raise AuthError("账号已停用")

    user.last_login_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    write_audit(
        db, action="login", username=user.username, user_id=user.id, ip=get_client_ip(request)
    )
    return Envelope(
        data={
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "user": {"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name},
        }
    )


@router.get("/me", response_model=Envelope)
async def me(user=Depends(get_current_user)) -> Envelope:
    return Envelope(
        data={"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name}
    )
