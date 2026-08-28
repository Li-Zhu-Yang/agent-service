"""运营后台接口（管理员）：工单 / 报表 / 会话查看 / 概览。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from api.dependencies import DbSession, require_admin
from core.exceptions import NotFoundError
from models.conversation import Conversation
from models.message import Message
from models.ticket import Ticket
from schemas.admin import DailyReportOut, OverviewOut, TicketOut, TicketUpdate
from schemas.common import Envelope
from schemas.conversation import ConversationOut, MessageOut
from services.audit import write_audit
from services.report import generate_daily_report, overview

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/overview", response_model=Envelope[OverviewOut])
async def admin_overview(db: DbSession) -> Envelope[OverviewOut]:
    data = await overview(db)
    return Envelope(data=OverviewOut.model_validate(data))


@router.get("/tickets", response_model=Envelope[list[TicketOut]])
async def list_tickets(db: DbSession, status: str = "", limit: int = 100) -> Envelope[list[TicketOut]]:
    stmt = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
    if status:
        stmt = select(Ticket).where(Ticket.status == status).order_by(Ticket.id.desc()).limit(limit)
    tickets = db.scalars(stmt).all()
    return Envelope(data=[TicketOut.model_validate(t) for t in tickets])


@router.get("/tickets/{ticket_id}", response_model=Envelope[TicketOut])
async def ticket_detail(ticket_id: int, db: DbSession) -> Envelope[TicketOut]:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise NotFoundError("工单不存在")
    return Envelope(data=TicketOut.model_validate(t))


@router.patch("/tickets/{ticket_id}", response_model=Envelope[TicketOut])
async def update_ticket(
    ticket_id: int, payload: TicketUpdate, db: DbSession
) -> Envelope[TicketOut]:
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
    return Envelope(data=TicketOut.model_validate(t))


@router.get("/reports/daily", response_model=Envelope[DailyReportOut])
async def daily_report(db: DbSession, date: str = "") -> Envelope[DailyReportOut]:
    """查询某日报表；未生成时自动生成。"""
    report_date = dt.date.fromisoformat(date) if date else dt.date.today()
    report = generate_daily_report(db, report_date)
    return Envelope(data=DailyReportOut.model_validate(report))


@router.post("/reports/generate", response_model=Envelope)
async def generate_report(db: DbSession, date: str = "") -> Envelope:
    report_date = dt.date.fromisoformat(date) if date else dt.date.today()
    report = generate_daily_report(db, report_date)
    write_audit(db, action="report_generate", resource=str(report_date))
    return Envelope(data={"report_date": report.report_date.isoformat(), "generated": True})


@router.get("/conversations", response_model=Envelope[list[ConversationOut]])
async def list_conversations(
    db: DbSession, limit: int = Query(50, ge=1, le=200), status: str = ""
) -> Envelope[list[ConversationOut]]:
    stmt = select(Conversation).order_by(Conversation.id.desc()).limit(limit)
    if status:
        stmt = select(Conversation).where(Conversation.status == status).order_by(Conversation.id.desc()).limit(limit)
    convs = db.scalars(stmt).all()
    return Envelope(data=[ConversationOut.model_validate(c) for c in convs])


@router.get("/conversations/{session_id}/messages", response_model=Envelope[list[MessageOut]])
async def conversation_messages(session_id: str, db: DbSession) -> Envelope[list[MessageOut]]:
    conv = db.scalar(select(Conversation).where(Conversation.session_id == session_id))
    if conv is None:
        raise NotFoundError("会话不存在")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
    ).all()
    return Envelope(data=[MessageOut.model_validate(m) for m in msgs])
