"""会话接口模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    intent: str
    confidence: float
    doc_sources: list | None
    need_human: bool
    from_cache: bool
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    session_id: str
    title: str
    intent_summary: str
    status: str
    last_message: str
    message_count: int
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
