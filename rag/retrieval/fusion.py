"""结果融合：RRF（Reciprocal Rank Fusion）。

对多路检索结果按排名融合，抑制单一检索器分数尺度差异带来的偏差。
"""
from __future__ import annotations

from typing import Any

RRF_K = 60


def rrf_fuse(ranked_lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """多路结果（各自已按相关性降序）融合为一个排序列表。"""
    acc: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            key = item["id"]
            if key not in acc:
                acc[key] = item
                scores[key] = 0.0
            scores[key] += 1.0 / (RRF_K + rank + 1)

    fused = []
    for key, score in scores.items():
        item = dict(acc[key])
        item["rrf_score"] = round(score, 6)
        fused.append(item)
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused
