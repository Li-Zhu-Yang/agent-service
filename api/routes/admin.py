"""运营后台接口（管理员）：工单 / 报表 / 会话查看 / 概览。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from api.dependencies import DbSession
from core.exceptions import NotFoundError
from models.conversation import Conversation
from models.message import Message
from models.ticket import Ticket
from schemas.admin import TicketUpdate
from schemas.common import Envelope
from system.audit import write_audit
from system.auth import require_admin
from system.report import generate_daily_report, overview

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/overview", response_model=Envelope)
async def admin_overview(db: DbSession) -> Envelope:
    data = await overview(db)
    return Envelope(data=data)


@router.get("/tickets", response_model=Envelope)
async def list_tickets(db: DbSession, status: str = "", limit: int = 100) -> Envelope:
    stmt = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
    if status:
        stmt = select(Ticket).where(Ticket.status == status).order_by(Ticket.id.desc()).limit(limit)
    tickets = db.scalars(stmt).all()
    return Envelope(data=[_ticket_to_dict(t) for t in tickets])


def _ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "ticket_no": t.ticket_no,
        "session_id": t.session_id,
        "customer_text": t.customer_text,
        "issue_summary": t.issue_summary,
        "intent": t.intent,
        "confidence": t.confidence,
        "priority": t.priority,
        "status": t.status,
        "assigned_to": t.assigned_to,
        "contact": t.contact,
        "resolved": t.resolved,
        "transcript": t.transcript,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/tickets/{ticket_id}", response_model=Envelope)
async def ticket_detail(ticket_id: int, db: DbSession) -> Envelope:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise NotFoundError("工单不存在")
    return Envelope(data=_ticket_to_dict(t))


@router.patch("/tickets/{ticket_id}", response_model=Envelope)
async def update_ticket(
    ticket_id: int, payload: TicketUpdate, db: DbSession, _=Depends(require_admin)
) -> Envelope:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise NotFoundError("工单不存在")
    if payload.status is not None:
        t.status = payload.status
    if payload.assigned_to is not None:
        t.assigned_to = payload.assigned_to
    if payload.resolved is not None:
        t.resolved = payload.resolved
    if payload.contact is not None:
        t.contact = payload.contact
    if t.status == "closed":
        t.closed_at = dt.datetime.now(dt.timezone.utc)
        t.resolved = True
    db.commit()
    write_audit(db, action="ticket_update", resource=t.ticket_no, detail=payload.model_dump())
    return Envelope(data=_ticket_to_dict(t))


@router.get("/reports/daily", response_model=Envelope)
async def daily_report(db: DbSession, date: str = "") -> Envelope:
    """查询某日报表；未生成时自动生成。"""
    report_date = dt.date.fromisoformat(date) if date else dt.date.today()
    report = generate_daily_report(db, report_date)
    return Envelope(
        data={
            "report_date": report.report_date.isoformat(),
            "total_questions": report.total_questions,
            "resolved_questions": report.resolved_questions,
            "unresolved_questions": report.unresolved_questions,
            "transferred_count": report.transferred_count,
            "high_frequency": report.high_frequency,
            "intent_distribution": report.intent_distribution,
            "avg_latency_ms": report.avg_latency_ms,
            "cache_hit_rate": report.cache_hit_rate,
        }
    )


@router.post("/reports/generate", response_model=Envelope)
async def generate_report(db: DbSession, date: str = "") -> Envelope:
    report_date = dt.date.fromisoformat(date) if date else dt.date.today()
    report = generate_daily_report(db, report_date)
    write_audit(db, action="report_generate", resource=str(report_date))
    return Envelope(data={"report_date": report.report_date.isoformat(), "generated": True})


@router.get("/conversations", response_model=Envelope)
async def list_conversations(
    db: DbSession, limit: int = Query(50, ge=1, le=200), status: str = ""
) -> Envelope:
    stmt = select(Conversation).order_by(Conversation.id.desc()).limit(limit)
    if status:
        stmt = select(Conversation).where(Conversation.status == status).order_by(Conversation.id.desc()).limit(limit)
    convs = db.scalars(stmt).all()
    return Envelope(
        data=[
            {
                "session_id": c.session_id,
                "title": c.title,
                "intent_summary": c.intent_summary,
                "status": c.status,
                "last_message": c.last_message,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in convs
        ]
    )


@router.get("/conversations/{session_id}/messages", response_model=Envelope)
async def conversation_messages(session_id: str, db: DbSession) -> Envelope:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is None:
        raise NotFoundError("会话不存在")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
    ).all()
    return Envelope(
        data=[
            {
                "role": m.role,
                "content": m.content,
                "intent": m.intent,
                "confidence": m.confidence,
                "doc_sources": m.doc_sources,
                "need_human": m.need_human,
                "from_cache": m.from_cache,
                "latency_ms": m.latency_ms,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]
    )
