"""重排序：基于 RRF 分数 + 标题命中 + 原文命中微调排序。

原则：融合分是主序；标题包含查询关键词、原文包含完整查询句，则小幅加权。
"""
from __future__ import annotations

from typing import Any

from rag.retrieval.tokenizer import tokenize


def rerank(
    items: list[dict[str, Any]],
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    q_lower = query.lower().strip()
    q_tokens = set(tokenize(query))

    def boost(item: dict[str, Any]) -> float:
        title = (item.get("title") or "").lower()
        chunk = (item.get("chunk") or "").lower()
        score = item.get("rrf_score", 0.0) or item.get("score", 0.0)
        w = 0.0
        if q_lower and (q_lower in title or q_lower in chunk):
            w += 0.15  # 完整查询句命中
        if q_tokens and title:
            hit = sum(1 for t in q_tokens if t in title)
            w += 0.05 * hit  # 标题关键词命中
        return score + w

    ranked = sorted(items, key=boost, reverse=True)
    if top_k:
        ranked = ranked[:top_k]
    for item in ranked:
        item["final_score"] = round(boost(item), 6)
    return ranked
