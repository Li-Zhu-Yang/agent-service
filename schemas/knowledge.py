"""知识库接口模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    doc_id: str
    title: str
    source: str
    file_type: str
    status: str
    chunk_count: int
    content_length: int
    category: str
    error: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class TextIngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1, description="正文内容")
    category: str = ""
    doc_id: str = ""


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(4, ge=1, le=20)


class ChunkOut(BaseModel):
    id: str
    doc_id: str
    title: str
    chunk: str
    score: float
    metadata: dict


class IngestResult(BaseModel):
    doc_id: str
    title: str
    chunk_count: int
    char_count: int
