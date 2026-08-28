"""知识检索节点：多路检索（向量 + BM25 → RRF → 重排）。

问候 / 转人工 / 投诉类意图不检索知识库。
"""
from __future__ import annotations

from agent.graph.state import ChatState
from bootstrap.settings import settings
from rag.retrieval.retriever import retrieve

SKIP_RETRIEVAL_INTENTS = {"greeting", "human", "complaint"}


async def retrieval_node(state: ChatState) -> ChatState:
    text = state.get("user_input", "")
    intent = state.get("intent", "other")
    if intent in SKIP_RETRIEVAL_INTENTS:
        return {"retrieved_docs": [], "no_knowledge": False}

    docs = await retrieve(text, top_k=settings.retrieval_rerank_top_k)
    return {
        "retrieved_docs": docs,
        "no_knowledge": not docs,
    }
