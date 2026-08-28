"""知识库文档表：入库文档的元数据。"""
from __future__ import annotations

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(300), default="")  # 原文件名
    file_type: Mapped[str] = mapped_column(String(16), default="md")  # pdf | docx | md | txt
    status: Mapped[str] = mapped_column(String(16), default="ingesting")  # ingesting | ready | failed
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(64), default="")
    error: Mapped[str] = mapped_column(String(500), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
