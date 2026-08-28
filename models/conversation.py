"""会话表：一次客服对话的聚合根。"""
from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="新会话")
    intent_summary: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | closed | transferred
    # 最近一条消息，用于列表预览
    last_message: Mapped[str] = mapped_column(String(500), default="")
    message_count: Mapped[int] = mapped_column(default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
