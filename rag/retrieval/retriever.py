"""多路检索器：向量（Chroma）+ BM25 关键词，混合召回。

BM25 索引从向量库全量分块惰性构建，入库后通过 invalidate_bm25_cache() 失效重建。
分词见 rag/retrieval/tokenizer.py（中文双字切分，无外部分词依赖）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bootstrap.settings import settings
from core.vector_store import vector_store
from rag.retrieval.fusion import rrf_fuse
from rag.retrieval.reranker import rerank
from rag.retrieval.tokenizer import tokenize

logger = logging.getLogger(__name__)


class BM25Index:
    """进程内 BM25 索引，基于向量库全量分块。"""

    def __init__(self) -> None:
        self._bm25 = None
        self._items: list[dict[str, Any]] = []
        self._corpus_tokens: list[list[str]] = []
        self._building = False

    def invalidate(self) -> None:
        self._bm25 = None
        self._items = []
        self._corpus_tokens = []

    async def _build(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            chunks = await vector_store.all_chunks()
            self._items = chunks
            self._corpus_tokens = [tokenize(c["chunk"]) for c in chunks]
            if not chunks:
                # 空知识库：跳过构建，避免 rank_bm25 空语料除零
                self._bm25 = None
                return
            try:
                from rank_bm25 import BM25Okapi

                self._bm25 = BM25Okapi(self._corpus_tokens)
            except ImportError:
                logger.warning("未安装 rank_bm25，BM25 检索不可用")
                self._bm25 = None
        finally:
            self._building = False

    async def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self._bm25 is None:
            await self._build()
        if self._bm25 is None or not self._corpus_tokens:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        try:
            scores = self._bm25.get_scores(q_tokens)
        except Exception:
            return []
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[dict[str, Any]] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                break
            item = self._items[i]
            m: dict = item.get("metadata") or {}
            out.append(
                {
                    "id": item.get("id", ""),
                    "doc_id": m.get("doc_id", ""),
                    "title": m.get("title", ""),
                    "chunk": item.get("chunk", ""),
                    "score": round(float(scores[i]), 4),
                    "metadata": m,
                }
            )
        return out


_bm25 = BM25Index()


def invalidate_bm25_cache() -> None:
    _bm25.invalidate()


async def vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
    return await vector_store.query(query, top_k=top_k)


async def bm25_search(query: str, top_k: int) -> list[dict[str, Any]]:
    try:
        return await asyncio.wait_for(_bm25.search(query, top_k), timeout=settings.retrieval_timeout)
    except asyncio.TimeoutError:
        logger.warning("BM25 检索超时")
        return []


async def hybrid_search(
    query: str, top_k: int | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """多路召回：返回 (向量结果, BM25结果)。"""
    k = top_k or settings.retrieval_top_k
    return await asyncio.gather(vector_search(query, k), bm25_search(query, k))


async def retrieve(
    query: str, top_k: int | None = None
) -> list[dict[str, Any]]:
    """完整检索流水线：向量 + BM25 多路召回 → RRF 融合 → 重排。"""
    k = top_k or settings.retrieval_top_k
    vec_results, bm25_results = await hybrid_search(query, top_k=k)
    fused = rrf_fuse([vec_results, bm25_results])
    if not fused:
        # 向量与 BM25 均空（例如知识库为空）
        return []
    ranked = rerank(fused, query, top_k=k)
    return ranked
