"""对话接口模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")
    session_id: str = Field("", description="会话 ID，空则服务端新建")
    user_id: int | None = None
