"""入库流水线：文本/文件 → 分块 → 向量化 → Chroma 写入。

幂等：同一 doc_id 重复入库会先删除旧分块再写入。
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from core.exceptions import AppError
from core.vector_store import vector_store
from rag.ingestion.chunker import chunk_text
from rag.ingestion.parser import parse_file, parse_text
from rag.retrieval.retriever import invalidate_bm25_cache

logger = logging.getLogger(__name__)


def new_doc_id() -> str:
    return uuid.uuid4().hex


async def ingest_text(
    doc_id: str,
    title: str,
    text: str,
    source: str = "",
    category: str = "",
    max_chars: int = 400,
) -> dict[str, Any]:
    """把纯文本按行业分块规则入库。"""
    text = parse_text(text)
    if not text:
        raise AppError("文档内容为空，无法入库")

    chunks = chunk_text(text, doc_title=title, max_chars=max_chars)
    if not chunks:
        raise AppError("分块结果为空，无法入库")

    # 幂等：先清旧分块
    await vector_store.delete_doc(doc_id)

    ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "title": title,
            "source": source,
            "category": category,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    await vector_store.add_chunks(doc_id, [c.text for c in chunks], metadatas, ids)
    invalidate_bm25_cache()
    return {
        "doc_id": doc_id,
        "title": title,
        "chunk_count": len(chunks),
        "char_count": sum(len(c.text) for c in chunks),
    }


async def ingest_file(
    path: str | Path,
    title: str | None = None,
    doc_id: str | None = None,
    category: str = "",
) -> dict[str, Any]:
    """解析文件并入库。"""
    p = Path(path)
    if not p.exists():
        raise AppError(f"文件不存在: {p}")
    text = parse_file(p)
    return await ingest_text(
        doc_id=doc_id or new_doc_id(),
        title=title or p.stem,
        text=text,
        source=p.name,
        category=category,
    )
