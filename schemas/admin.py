"""运营后台接口模型。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class TicketOut(BaseModel):
    id: int
    ticket_no: str
    session_id: str
    customer_text: str
    issue_summary: str
    intent: str
    confidence: float
    priority: str
    status: str
    assigned_to: str
    contact: str
    resolved: bool
    transcript: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketUpdate(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    resolved: bool | None = None
    contact: str | None = None


class DailyReportOut(BaseModel):
    report_date: date
    total_questions: int
    resolved_questions: int
    unresolved_questions: int
    transferred_count: int
    high_frequency: dict[str, int]
    intent_distribution: dict[str, int]
    avg_latency_ms: float
    cache_hit_rate: float
    created_at: datetime

    model_config = {"from_attributes": True}


class OverviewOut(BaseModel):
    total_conversations: int
    today_questions: int
    open_tickets: int
    total_documents: int
    vector_chunks: int
