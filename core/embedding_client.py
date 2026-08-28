"""Embedding 客户端（可插拔）。

providers:
- chroma_local      默认。Chroma 内置 ONNX MiniLM 本地模型，免 key、轻量（首次使用会下载模型）。
- hash             零依赖哈希向量（旧项目同款思路）。无下载、无 key，配合 BM25 可离线开箱即用。
- dashscope        阿里云百炼文本向量（OpenAI 兼容 endpoint）。
- openai_compatible任意 OpenAI 兼容向量服务（如 SiliconFlow bge-m3）。

当 chroma_local 的模型加载失败时自动回退 hash，保证项目开箱可用。
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Callable

from bootstrap.settings import settings

logger = logging.getLogger(__name__)

HASH_DIM = 512


class _HashEmbedder:
    """字符 n-gram 哈希向量。零依赖，质量一般但稳定，适合兜底/离线。"""

    name = "hash"

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * HASH_DIM
        norm_text = text.lower().strip()
        if not norm_text:
            return vec
        tokens = [c for c in norm_text]
        grams: list[str] = list(tokens)
        for i in range(len(tokens) - 1):  # 双字 gram 增强中文表达
            grams.append(tokens[i] + tokens[i + 1])
        for g in grams:
            h = int.from_bytes(hashlib.md5(g.encode("utf-8")).digest()[:8], "big")
            vec[h % HASH_DIM] += 1.0
        # L2 归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class EmbeddingClient:
    """统一向量化入口。"""

    def __init__(self) -> None:
        self.provider = settings.embedding_provider
        self._chroma_fn: Callable[[list[str]], list[list[float]]] | None = None
        self._dashscope_client = None
        self._openai_compatible_client = None
        self.hash_embedder = _HashEmbedder()
        self._resolved_provider: str | None = None

    # ---- 初始化 ----
    def _load_chroma_fn(self) -> Callable[[list[str]], list[list[float]]]:
        if self._chroma_fn is not None:
            return self._chroma_fn
        try:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

            fn = DefaultEmbeddingFunction()
            # 触发一次加载，失败立刻回退 hash
            fn(["测试"])
            self._chroma_fn = fn
            logger.info("Embedding: chroma_local(MiniLM ONNX) 就绪")
            return fn
        except Exception as exc:
            logger.warning("Embedding: chroma_local 模型加载失败(%s)，回退 hash 向量", exc)
            raise

    def _dashscope_embed(self, texts: list[str]) -> list[list[float]]:
        # 同步客户端：由调用方 asyncio.to_thread 包装，避免事件循环冲突
        if self._dashscope_client is None:
            from openai import OpenAI

            self._dashscope_client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        resp = self._dashscope_client.embeddings.create(
            model=settings.embedding_model or "text-embedding-v3",
            input=texts,
        )
        return [d.embedding for d in resp.data]

    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        if self._openai_compatible_client is None:
            from openai import OpenAI

            self._openai_compatible_client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url or "https://api.openai.com/v1",
            )
        resp = self._openai_compatible_client.embeddings.create(
            model=settings.embedding_model or "text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in resp.data]

    def _resolve(self) -> None:
        """确定最终生效的 provider。"""
        if self._resolved_provider is not None:
            return
        provider = settings.embedding_provider
        if provider == "chroma_local":
            try:
                self._load_chroma_fn()
                provider = "chroma_local"
            except Exception:
                provider = "hash"
        self._resolved_provider = provider
        logger.info("Embedding: 生效 provider=%s", provider)

    # ---- 对外接口 ----
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._resolve()
        if self._resolved_provider == "chroma_local":
            return list(self._chroma_fn(texts))  # type: ignore[union-attr]
        if self._resolved_provider == "dashscope":
            return self._dashscope_embed(texts)
        if self._resolved_provider == "openai_compatible":
            return self._openai_embed(texts)
        return self.hash_embedder(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def effective_provider(self) -> str:
        self._resolve()
        return self._resolved_provider  # type: ignore[return-value]


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
