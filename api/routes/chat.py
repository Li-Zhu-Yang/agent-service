"""对话接口（SSE 流式）。

前端通过 fetch + ReadableStream 消费，事件类型：
- session  {session_id}
- token    {delta: 增量文本}
- error    {message}
- done     {session_id, intent, need_human, ticket_no, answer, meta}
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from agent.agent import agent, load_context, save_context
from agent.graph.state import ChatState, initial_state
from api.dependencies import DbSession, get_client_ip
from core.exceptions import RateLimitError
from core.rate_limit import rate_limiter
from models.conversation import Conversation
from models.message import Message
from schemas.chat import ChatRequest
from system.auth import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _load_db_history(db, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is None:
        return []
    msgs = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.desc())
        .limit(limit)
    ).all()
    msgs = list(reversed(msgs))
    return [{"role": m.role, "content": m.content} for m in msgs]


async def _persist(
    db,
    session_id: str,
    user_id: int | None,
    user_content: str,
    answer: str,
    intent: str,
    need_human: bool,
    meta: dict,
    doc_sources: list[dict],
) -> None:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is None:
        conv = Conversation(
            session_id=session_id,
            user_id=user_id,
            title=user_content[:30],
            status="transferred" if need_human else "active",
        )
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content=user_content, intent=intent))
    db.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer,
            intent=intent,
            doc_sources=doc_sources,
            need_human=need_human,
            from_cache=bool(meta.get("from_cache", False)),
            latency_ms=int(meta.get("latency_ms", 0) or 0),
            tokens_used=int(meta.get("tokens_used", 0) or 0),
        )
    )
    conv.last_message = answer[:200]
    conv.message_count += 2
    conv.intent_summary = intent
    if need_human:
        conv.status = "transferred"
    db.commit()


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    ip = get_client_ip(request)
    allowed, _count = await rate_limiter.allow(f"ip:{ip}")
    if not allowed:
        raise RateLimitError()

    session_id = (payload.session_id or "").strip() or uuid.uuid4().hex

    user = await get_optional_user(authorization, db)
    user_id = user.id if user else None

    # 上下文：短期记忆（Redis/内存），缺失则回退数据库最近消息
    history, history_intents, meta = await load_context(session_id, db)
    if not history:
        history = _load_db_history(db, session_id)

    async def event_gen() -> AsyncIterator[str]:
        yield _sse({"session_id": session_id})
        state = initial_state(
            session_id=session_id,
            user_input=payload.message,
            user_id=user_id,
            history=history,
            meta=meta,
        )
        state["history_intents"] = history_intents
        final: ChatState = dict(state)
        try:
            async for mode, chunk in agent.graph.astream(state, stream_mode=["custom", "updates"]):
                if mode == "custom":
                    yield _sse({"delta": str(chunk)})
                else:  # updates
                    for _node, upd in chunk.items():
                        final.update(upd)
        except Exception as exc:  # 生成异常：向客户端发错误并回退
            logger.exception("对话流式生成异常")
            yield _sse({"error": {"message": f"生成失败：{exc}"}})
            answer = "抱歉，服务暂时开小差了，请稍后再试。"
            final["answer"] = answer
            final["need_human"] = False

        answer = final.get("answer", "")
        if not answer:
            answer = "抱歉，暂时无法生成回答，请换一种说法或直接说「转人工」。"
        intent = final.get("intent", "")
        need_human = bool(final.get("need_human"))
        ticket_no = final.get("ticket_no", "")
        meta_final = dict(final.get("meta") or {})
        meta_final["from_cache"] = bool(final.get("from_cache", False))
        doc_sources = [
            {"doc_id": d.get("doc_id"), "title": d.get("title")}
            for d in (final.get("retrieved_docs") or [])
        ]

        try:
            await _persist(
                db, session_id, user_id, payload.message, answer, intent, need_human,
                meta_final, doc_sources,
            )
            await save_context(
                session_id, payload.message, answer,
                {"intent": intent, **meta_final},
            )
        except Exception as exc:
            logger.error("持久化失败: %s", exc)

        yield _sse(
            {
                "session_id": session_id,
                "intent": intent,
                "need_human": need_human,
                "ticket_no": ticket_no,
                "answer": answer,
                "meta": meta_final,
            }
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
