"""知识图谱检索（可选模块）。

当前为接口占位：接入 Neo4j 后在此实现实体/关系查询，并在
rag.retrieval.retriever.retrieve 中把图谱结果并入融合链路。

接入示例：
    class Neo4jGraphQuery:
        def __init__(self, uri, user, password): ...
        def query_related(self, entity: str) -> list[dict]: ...
        async def search(self, query_text: str, top_k: int) -> list[dict]: ...
"""
from __future__ import annotations

from typing import Any


class GraphQuery:
    """图谱检索接口。未启用时返回空，不影响主链路。"""

    enabled = False

    async def search(self, _query_text: str, _top_k: int) -> list[dict[str, Any]]:
        return []


graph_query = GraphQuery()
