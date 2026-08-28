"""分块与检索测试：行业分块规则 + 混合检索（向量+BM25→RRF→重排）。"""
from __future__ import annotations

import pytest

from rag.ingestion.chunker import chunk_text
from rag.retrieval.retriever import retrieve

from tests.conftest import seed_kb


def test_chunker_keeps_qa_pair():
    """问-答配对不应被拆散。"""
    text = "问：支持七天无理由退货吗？\n答：支持。自签收之日起 7 天内可申请无理由退货。\n\n其他补充说明。"
    chunks = chunk_text(text, doc_title="退换货")
    assert chunks, "应至少产生一个分块"
    joined = " ".join(c.text for c in chunks)
    assert "七天无理由退货" in joined
    assert "签收之日起" in joined


def test_chunker_splits_by_title():
    """按标题切分应保留标题链。"""
    text = "# 退款流程\n\n审核通过后原路退回。\n\n## 到账时间\n\n一般 1-3 个工作日。"
    chunks = chunk_text(text, doc_title="售后")
    assert chunks
    assert any("售后" in c.title for c in chunks)
    assert any("退款流程" in c.title for c in chunks)


async def test_retrieve_with_seeded_kb():
    await seed_kb()
    results = await retrieve("退款多久到账", top_k=4)
    assert results, "应检索到退款相关内容"
    top = results[0]
    assert top.get("chunk")
    assert top.get("doc_id") == "test-doc-1"
    assert top.get("final_score", 0) > 0


async def test_retrieve_empty_kb():
    results = await retrieve("随便问问", top_k=4)
    assert results == []
