"""向量库封装（Chroma PersistentClient，本地文件，轻量）。

对外提供 async 接口；Chroma 与 embedding 均为同步阻塞操作，内部用 asyncio.to_thread
包装，避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bootstrap.settings import settings
from core.embedding_client import get_embedding_client

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self.embedding = get_embedding_client()

    def _ensure(self):
        if self._collection is not None:
            return self._collection
        import chromadb

        if self._client is None:
            self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    async def _sync(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    # ---- 写入 ----
    async def add_chunks(
        self,
        doc_id: str,
        chunks: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> int:
        """批量写入分块。调用方保证 chunks/metadatas/ids 长度一致。"""
        col = await self._sync(self._ensure)

        def _do():
            embeddings = self.embedding.embed_texts(chunks)
            col.add(ids=ids, documents=chunks, metadatas=metadatas, embeddings=embeddings)
            return len(chunks)

        return await self._sync(_do)

    async def delete_doc(self, doc_id: str) -> int:
        """按 doc_id 删除一个文档的全部分块，返回删除数量。"""

        def _do() -> int:
            col = self._ensure()
            existing = col.get(where={"doc_id": doc_id})
            if existing and existing.get("ids"):
                col.delete(ids=existing["ids"])
                return len(existing["ids"])
            return 0

        return await self._sync(_do)

    # ---- 查询 ----
    async def query(
        self,
        query_text: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """向量相似度检索，返回 [{doc_id, title, chunk, score, metadata}]（cosine 距离转相似度）。"""
        k = top_k or settings.retrieval_top_k

        def _do() -> list[dict[str, Any]]:
            col = self._ensure()
            q = self.embedding.embed_query(query_text)
            res = col.query(query_embeddings=[q], n_results=k, where=where)
            out: list[dict[str, Any]] = []
            if not res.get("ids"):
                return out
            ids = res["ids"][0]
            dists = res["distances"][0] if res.get("distances") else [0.0] * len(ids)
            docs = res["documents"][0] if res.get("documents") else [""] * len(ids)
            metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(ids)
            for i, _id in enumerate(ids):
                m: dict = metas[i] or {}
                # cosine 距离 ∈ [0,2]，相似度 = 1 - dist/2
                score = 1.0 - float(dists[i]) / 2.0
                out.append(
                    {
                        "id": _id,
                        "doc_id": m.get("doc_id", ""),
                        "title": m.get("title", ""),
                        "chunk": docs[i],
                        "score": round(score, 4),
                        "metadata": m,
                    }
                )
            return out

        try:
            return await asyncio.wait_for(self._sync(_do), timeout=settings.retrieval_timeout)
        except asyncio.TimeoutError:
            logger.warning("向量检索超时")
            return []

    # ---- 管理 ----
    async def count(self) -> int:
        def _do() -> int:
            col = self._ensure()
            return col.count()

        return await self._sync(_do)

    async def list_doc_ids(self) -> set[str]:
        def _do() -> set[str]:
            col = self._ensure()
            data = col.get(include=["metadatas"])
            ids: set[str] = set()
            for m in data.get("metadatas") or []:
                if m and m.get("doc_id"):
                    ids.add(m["doc_id"])
            return ids

        return await self._sync(_do)

    async def all_chunks(self) -> list[dict[str, Any]]:
        """返回库中全部分块（BM25 建立索引用）。"""

        def _do() -> list[dict[str, Any]]:
            col = self._ensure()
            data = col.get(include=["documents", "metadatas"])
            out = []
            ids = data.get("ids") or []
            docs = data.get("documents") or []
            metas = data.get("metadatas") or []
            for i, chunk in enumerate(docs):
                out.append(
                    {
                        "id": ids[i],
                        "chunk": chunk,
                        "metadata": metas[i] if i < len(metas) else {},
                    }
                )
            return out

        return await self._sync(_do)

    async def get_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        def _do() -> list[dict[str, Any]]:
            col = self._ensure()
            data = col.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
            out = []
            for i, chunk in enumerate(data.get("documents") or []):
                out.append({"chunk": chunk, "metadata": (data["metadatas"] or [{}])[i]})
            return out

        return await self._sync(_do)

    async def reset(self) -> None:
        def _do():
            col = self._ensure()
            data = col.get(include=[])
            ids = data.get("ids") or []
            if ids:
                col.delete(ids=ids)

        await self._sync(_do)


# 全局单例
vector_store = VectorStore()

# 预初始化：在模块导入时（无事件循环）打开 Chroma 并缓存句柄。
# 原因：chromadb 1.x 在 asyncio 事件循环运行期间首次 PersistentClient 会卡死/崩溃，
# 提前在导入阶段预热可让后续请求命中进程内缓存，规避该问题。
try:
    vector_store._ensure()
    logger.info("向量库已预初始化: %s", settings.chroma_dir)
except Exception as exc:  # pragma: no cover - 仅防御性，不阻断启动
    logger.warning("向量库预初始化失败（首次请求时将重试）: %s", exc)
