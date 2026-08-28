"""工单表：转人工后的问题归档记录。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 用户最后一条消息
    customer_text: Mapped[str] = mapped_column(Text, default="")
    issue_summary: Mapped[str] = mapped_column(Text, default="")
    intent: Mapped[str] = mapped_column(String(32), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # normal | high
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | accepted | closed
    # 完整对话记录（用户消息 + 助手消息）
    transcript: Mapped[list | None] = mapped_column(JSON, nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(64), default="")
    contact: Mapped[str] = mapped_column(String(128), default="")
    resolved: Mapped[bool] = mapped_column(default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
