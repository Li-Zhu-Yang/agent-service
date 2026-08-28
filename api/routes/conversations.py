"""会话管理接口：查询 / 删除。"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from agent.memory import short_term
from api.dependencies import DbSession
from core.exceptions import NotFoundError
from models.conversation import Conversation
from models.message import Message
from schemas.common import Envelope

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/{session_id}", response_model=Envelope)
async def get_conversation(session_id: str, db: DbSession) -> Envelope:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is None:
        raise NotFoundError("会话不存在")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
    ).all()
    return Envelope(
        data={
            "session_id": conv.session_id,
            "title": conv.title,
            "status": conv.status,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "intent": m.intent,
                    "need_human": m.need_human,
                    "doc_sources": m.doc_sources,
                    "created_at": m.created_at.isoformat(),
                }
                for m in msgs
            ],
        }
    )


@router.delete("/{session_id}", response_model=Envelope)
async def delete_conversation(session_id: str, db: DbSession) -> Envelope:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is not None:
        db.delete(conv)
        db.commit()
    await short_term.clear(session_id)
    return Envelope(data={"deleted": True})
