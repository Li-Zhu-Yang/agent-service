"""依赖注入：复用数据库会话与当前用户。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.database import get_db
from system.auth import get_current_user

# 会话依赖（必须用 Depends 包装，否则 FastAPI 误判为响应字段）
DbSession = Annotated[Session, Depends(get_db)]


def get_client_ip(request: Request) -> str:
    """获取客户端 IP（兼容反代 X-Forwarded-For）。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
