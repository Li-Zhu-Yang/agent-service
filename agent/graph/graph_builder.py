"""LangGraph 工作流构建器。

流程：intent → retrieval（可跳过）→ tool_call → response
条件边：
- 问候/转人工/投诉不检索知识库，直接进工具/回复节点。
"""
from __future__ import annotations

import logging
from functools import partial

from agent.graph.nodes.intent import intent_node
from agent.graph.nodes.response import response_node
from agent.graph.nodes.retrieval import retrieval_node, SKIP_RETRIEVAL_INTENTS
from agent.graph.nodes.tool_call import tool_call_node
from agent.graph.state import ChatState
from agent.tools.human_tool import HumanHandoffTool
from agent.tools.order_tool import OrderQueryTool
from agent.tools.refund_tool import RefundTool
from core.database import SessionLocal

logger = logging.getLogger(__name__)

_compiled_graph = None


def _route_from_intent(state: ChatState) -> str:
    if state.get("intent") in SKIP_RETRIEVAL_INTENTS:
        return "to_tool"
    return "to_retrieval"


def build_graph():
    """构建并编译 LangGraph 工作流。"""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ChatState)

    human_tool = HumanHandoffTool(session_factory=SessionLocal)
    order_tool = OrderQueryTool()
    refund_tool = RefundTool()

    graph.add_node("intent", intent_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node(
        "tool_call",
        partial(tool_call_node, human_tool=human_tool, order_tool=order_tool, refund_tool=refund_tool),
    )
    graph.add_node("response", response_node)

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        _route_from_intent,
        {"to_retrieval": "retrieval", "to_tool": "tool_call"},
    )
    graph.add_edge("retrieval", "tool_call")
    graph.add_edge("tool_call", "response")
    graph.add_edge("response", END)

    return graph.compile()


def get_graph():
    """惰性构建单例图。"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
        logger.info("LangGraph 工作流已构建")
    return _compiled_graph
