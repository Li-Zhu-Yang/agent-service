"""每日运营报表聚合。

按自然日统计：问题总量 / 解决量 / 未解决量 / 转人工量 / 高频问题 / 意图分布 / 响应时长 / 缓存命中。
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.conversation import Conversation
from models.daily_report import DailyReport
from models.message import Message

_NORMALIZE_RE = re.compile(r"[\W_]+")


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.lower())


def _day_range(d: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(d, dt.time.min)
    end = start + dt.timedelta(days=1)
    return start, end


def aggregate_day(db: Session, report_date: dt.date) -> dict:
    start, end = _day_range(report_date)

    user_msgs = db.scalars(
        select(Message).where(
            Message.role == "user", Message.created_at >= start, Message.created_at < end
        )
    ).all()
    assistant_msgs = db.scalars(
        select(Message).where(
            Message.role == "assistant", Message.created_at >= start, Message.created_at < end
        )
    ).all()

    total_questions = len(user_msgs)
    transferred = sum(1 for m in assistant_msgs if m.need_human)
    resolved = len(assistant_msgs) - transferred
    unresolved = total_questions - resolved

    # 高频问题（按归一化后文本）
    norm_counter: Counter[str] = Counter(_normalize(m.content) for m in user_msgs)
    # 保留原文用于展示
    orig_by_norm: dict[str, str] = {}
    for m in user_msgs:
        orig_by_norm.setdefault(_normalize(m.content), m.content[:100])
    high_frequency = {orig_by_norm[k]: v for k, v in norm_counter.most_common(10) if v >= 1}

    intent_dist = dict(Counter(m.intent or "other" for m in assistant_msgs))

    latencies = [m.latency_ms for m in assistant_msgs if m.latency_ms]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    cache_hit = sum(1 for m in assistant_msgs if m.from_cache) / len(assistant_msgs) if assistant_msgs else 0.0

    return {
        "report_date": report_date,
        "total_questions": total_questions,
        "resolved_questions": max(0, resolved),
        "unresolved_questions": max(0, unresolved),
        "transferred_count": transferred,
        "high_frequency": high_frequency,
        "intent_distribution": intent_dist,
        "avg_latency_ms": avg_latency,
        "cache_hit_rate": round(cache_hit, 4),
    }


def generate_daily_report(db: Session, report_date: dt.date | None = None) -> DailyReport:
    """生成（或更新）某天的报表并落库。"""
    report_date = report_date or dt.date.today()
    data = aggregate_day(db, report_date)
    report = db.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    if report is None:
        # 显式传 report_date，仅排除 data 中的重复副本，避免重复关键字参数
        report = DailyReport(
            report_date=report_date,
            **{k: v for k, v in data.items() if k != "report_date"},
        )
        db.add(report)
    else:
        for k, v in data.items():
            if k != "report_date":
                setattr(report, k, v)
    db.commit()
    return report


async def overview(db: Session) -> dict:
    """后台概览。"""
    from core.vector_store import vector_store

    today = dt.date.today()
    start, _end = _day_range(today)
    today_questions = db.scalar(
        select(func.count(Message.id)).where(
            Message.role == "user", Message.created_at >= start
        )
    ) or 0
    total_conversations = db.scalar(select(func.count(Conversation.id))) or 0
    from models.ticket import Ticket

    open_tickets = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.status != "closed")
    ) or 0
    from models.document import Document

    total_documents = db.scalar(select(func.count(Document.id))) or 0
    try:
        vector_chunks = await vector_store.count()
    except Exception:
        vector_chunks = 0
    return {
        "total_conversations": total_conversations,
        "today_questions": today_questions,
        "open_tickets": open_tickets,
        "total_documents": total_documents,
        "vector_chunks": vector_chunks,
    }
