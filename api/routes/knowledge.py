"""知识库管理接口（管理员）：上传 / 文本入库 / 检索测试 / 列表 / 删除。"""
from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select

from api.dependencies import DbSession
from core.exceptions import NotFoundError
from core.vector_store import vector_store
from models.document import Document
from rag.ingestion.pipeline import ingest_text
from rag.retrieval.retriever import retrieve
from schemas.common import Envelope
from schemas.knowledge import SearchRequest, TextIngestRequest
from system.audit import write_audit
from system.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_admin)],
)


@router.get("/documents", response_model=Envelope)
async def list_documents(db: DbSession) -> Envelope:
    docs = db.scalars(select(Document).order_by(Document.id.desc())).all()
    return Envelope(data=[_doc_to_dict(d) for d in docs])


def _doc_to_dict(d: Document) -> dict:
    return {
        "id": d.id,
        "doc_id": d.doc_id,
        "title": d.title,
        "source": d.source,
        "file_type": d.file_type,
        "status": d.status,
        "chunk_count": d.chunk_count,
        "content_length": d.content_length,
        "category": d.category,
        "error": d.error,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/upload", response_model=Envelope)
async def upload_document(file: UploadFile, db: DbSession, _=Depends(require_admin)) -> Envelope:
    ext = (file.filename or "md").rsplit(".", 1)[-1].lower()
    doc_id = uuid.uuid4().hex
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        from rag.ingestion.pipeline import ingest_file

        stats = await ingest_file(tmp_path, title=file.filename, doc_id=doc_id, category="上传")
        db.add(
            Document(
                doc_id=doc_id,
                title=file.filename or "未命名文档",
                source=file.filename or "",
                file_type=ext,
                status="ready",
                chunk_count=stats["chunk_count"],
                content_length=stats["char_count"],
                category="上传",
            )
        )
        db.commit()
        write_audit(db, action="knowledge_upload", resource=file.filename or "", detail=stats)
        return Envelope(data=stats)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/text", response_model=Envelope)
async def ingest_by_text(payload: TextIngestRequest, db: DbSession) -> Envelope:
    doc_id = payload.doc_id or uuid.uuid4().hex
    stats = await ingest_text(
        doc_id=doc_id, title=payload.title, text=payload.text, category=payload.category
    )
    db.add(
        Document(
            doc_id=doc_id,
            title=payload.title,
            source="",
            file_type="md",
            status="ready",
            chunk_count=stats["chunk_count"],
            content_length=stats["char_count"],
            category=payload.category or "文本录入",
        )
    )
    db.commit()
    write_audit(db, action="knowledge_ingest", resource=payload.title, detail=stats)
    return Envelope(data=stats)


@router.delete("/documents/{doc_id}", response_model=Envelope)
async def delete_document(doc_id: str, db: DbSession) -> Envelope:
    doc = db.scalar(select(Document).where(Document.doc_id == doc_id))
    if doc is None:
        raise NotFoundError("文档不存在")
    removed = await vector_store.delete_doc(doc_id)
    from rag.retrieval.retriever import invalidate_bm25_cache

    invalidate_bm25_cache()
    db.delete(doc)
    db.commit()
    write_audit(db, action="knowledge_delete", resource=doc.title, detail={"removed_chunks": removed})
    return Envelope(data={"deleted": True, "removed_chunks": removed})


@router.post("/search", response_model=Envelope)
async def search_knowledge(payload: SearchRequest) -> Envelope:
    """检索测试：直接看知识库命中结果。"""
    results = await retrieve(payload.query, top_k=payload.top_k)
    return Envelope(
        data=[
            {
                "id": r.get("id"),
                "doc_id": r.get("doc_id"),
                "title": r.get("title"),
                "chunk": r.get("chunk"),
                "score": r.get("final_score") or r.get("rrf_score") or r.get("score", 0),
            }
            for r in results
        ]
    )


@router.get("/documents/{doc_id}/chunks", response_model=Envelope)
async def document_chunks(doc_id: str) -> Envelope:
    chunks = await vector_store.get_chunks(doc_id)
    return Envelope(data=chunks)
