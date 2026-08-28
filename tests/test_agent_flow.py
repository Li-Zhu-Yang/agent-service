"""Agent 全链路测试：LangGraph 工作流（无需 LLM key，走规则+工具兜底）。"""
from __future__ import annotations

from sqlalchemy import select

from agent.agent import Agent
from models.ticket import Ticket

from tests.conftest import seed_kb

agent = Agent()


async def test_greeting_flow():
    state = await agent.answer(session_id="t1", user_input="你好")
    assert state["intent"] == "greeting"
    assert state["answer"]
    assert "您好" in state["answer"]
    assert state["need_human"] is False


async def test_human_handoff_creates_ticket(db_session):
    state = await agent.answer(session_id="t2", user_input="转人工客服")
    assert state["need_human"] is True
    assert state["tool_name"] == "human_handoff"
    ticket = db_session.scalar(select(Ticket).order_by(Ticket.id.desc()))
    assert ticket is not None
    assert ticket.session_id == "t2"
    assert "人工" in state["answer"]


async def test_refund_flow_with_knowledge():
    await seed_kb()
    state = await agent.answer(session_id="t3", user_input="我要退款")
    assert state["intent"] == "refund"
    # 无 LLM 时直接使用工具结果兜底
    assert state["answer"]
    assert "退款" in state["answer"]


async def test_order_query_tool():
    state = await agent.answer(session_id="t4", user_input="订单 12345678901 到哪了")
    assert state["intent"] == "query_order"
    assert state["tool_name"] == "query_order"
    assert "12345678901" in state["answer"]


async def test_no_knowledge_fallback():
    state = await agent.answer(session_id="t5", user_input="你们总部大楼有几层")
    # 无知识命中 → 兜底话术，并标记未解决
    assert state["answer"]
    assert state["meta"]["unresolved_rounds"] >= 1
