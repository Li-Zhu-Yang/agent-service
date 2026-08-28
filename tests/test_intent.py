"""意图识别测试：规则层（不依赖 LLM）。"""
from __future__ import annotations

import pytest

from agent.intent import classify_by_rule, classify_intent


@pytest.mark.parametrize(
    "text,expected",
    [
        ("你好", "greeting"),
        ("在吗", "greeting"),
        ("我要退款", "refund"),
        ("怎么退货", "refund"),
        ("订单查一下", "query_order"),
        ("快递到哪里了", "query_order"),
        ("冰箱坏了报修", "repair"),
        ("怎么申请维修", "repair"),
        ("转人工客服", "human"),
        ("我要投诉", "complaint"),
        ("怎么开发票", "invoice"),
        ("优惠券怎么用", "coupon"),
    ],
)
def test_classify_by_rule(text, expected):
    result = classify_by_rule(text)
    assert result is not None
    intent, conf, _reason = result
    assert intent == expected
    assert conf >= 0.8


async def test_classify_intent_no_llm():
    """无 LLM 时规则命中仍有效。"""
    result = await classify_intent("我要退货")
    assert result["intent"] == "refund"
    assert result["confidence"] >= 0.8

    result2 = await classify_intent("今天天气不错")
    # 无 LLM 时规则未命中 → other，置信度低
    assert result2["intent"] == "other"
    assert result2["confidence"] < 0.5


async def test_classify_intent_empty():
    result = await classify_intent("   ")
    assert result["intent"] == "other"
