"""审计日志：记录管理操作到 audit_logs 表。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.audit import AuditLog


def write_audit(
    db: Session,
    action: str,
    username: str = "",
    user_id: int | None = None,
    resource: str = "",
    detail: dict[str, Any] | None = None,
    ip: str = "",
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource=resource,
        detail=detail or {},
        ip=ip,
    )
    db.add(entry)
    db.commit()
    return entry
