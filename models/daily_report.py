"""每日运营报表表：高频问题 / 未解决问题 / 意图分布 / 响应时长聚合。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class DailyReport(Base, TimestampMixin):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(unique=True, index=True, nullable=False)

    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    resolved_questions: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_questions: Mapped[int] = mapped_column(Integer, default=0)
    transferred_count: Mapped[int] = mapped_column(Integer, default=0)

    # {query_text: count} 按次数降序
    high_frequency: Mapped[dict] = mapped_column(JSON, default=dict)
    # {intent: count}
    intent_distribution: Mapped[dict] = mapped_column(JSON, default=dict)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
