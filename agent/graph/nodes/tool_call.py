"""工具调用与分流节点（逻辑见 agent.dispatch）。"""
from __future__ import annotations

from agent.dispatch import dispatch_tool_call
from agent.graph.state import ChatState
from agent.tools.human_tool import HumanHandoffTool
from agent.tools.order_tool import OrderQueryTool
from agent.tools.refund_tool import RefundTool


async def tool_call_node(
    state: ChatState,
    human_tool: HumanHandoffTool,
    order_tool: OrderQueryTool,
    refund_tool: RefundTool,
) -> ChatState:
    return await dispatch_tool_call(state, human_tool, order_tool, refund_tool)
