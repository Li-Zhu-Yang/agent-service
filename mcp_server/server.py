"""MCP 协议服务端（stdio 传输）。

暴露工具（复用 agent.tools 的实现与 spec）：
- query_order        订单查询
- apply_refund       退款申请
- query_weather      天气查询（示例）
- knowledge_search   知识库检索
- human_handoff      创建转人工工单

运行：python -m mcp_server
"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent.tools.human_tool import HumanHandoffTool
from agent.tools.order_tool import OrderQueryTool
from agent.tools.refund_tool import RefundTool
from agent.tools.weather_tool import WeatherTool

logger = logging.getLogger(__name__)

mcp = FastMCP("ragent-cs", instructions="智享电器智能客服系统工具集")

_order_tool = OrderQueryTool()
_refund_tool = RefundTool()
_weather_tool = WeatherTool()
_human_tool = HumanHandoffTool()


@mcp.tool(name="query_order")
async def query_order(order_no: str = "", phone: str = "") -> str:
    """根据订单号或手机号查询订单状态、物流信息。"""
    return await _order_tool.run(order_no=order_no, phone=phone)


@mcp.tool(name="apply_refund")
async def apply_refund(order_no: str, reason: str = "") -> str:
    """为订单提交退款/退货申请。"""
    return await _refund_tool.run(order_no=order_no, reason=reason)


@mcp.tool(name="query_weather")
async def query_weather(city: str) -> str:
    """查询某城市天气（示例工具）。"""
    return await _weather_tool.run(city=city)


@mcp.tool(name="knowledge_search")
async def knowledge_search(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """在客服知识库中检索相关问题答案。"""
    from rag.retrieval.retriever import retrieve

    results = await retrieve(query, top_k=top_k)
    return [
        {"title": r.get("title", ""), "content": r.get("chunk", ""), "score": r.get("final_score", 0)}
        for r in results
    ]


@mcp.tool(name="human_handoff")
async def human_handoff(
    session_id: str,
    user_input: str,
    intent: str = "",
    confidence: float = 0.0,
    summary: str = "",
) -> str:
    """转接人工客服并创建问题工单，同步用户对话记录。"""
    return await _human_tool.run(
        session_id=session_id, user_input=user_input, intent=intent,
        confidence=confidence, summary=summary,
    )
