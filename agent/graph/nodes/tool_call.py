"""工具调用与分流节点。

- 触发转人工：用户主动要求 / 投诉 / 低置信 / 连续未解决轮数达阈值。
- 订单 / 退款意图：调用对应工具，结果为后续生成提供依据。
"""
from __future__ import annotations

import logging
import re

from agent.graph.state import ChatState
from agent.tools.human_tool import HumanHandoffTool
from agent.tools.order_tool import OrderQueryTool
from agent.tools.refund_tool import RefundTool
from bootstrap.settings import settings

logger = logging.getLogger(__name__)

_ORDER_NO_RE = re.compile(r"\d{11}")
_PHONE_RE = re.compile(r"1[3-9]\d{9}")


def _should_transfer(state: ChatState) -> tuple[bool, str]:
    intent = state.get("intent", "other")
    conf = state.get("intent_confidence", 0.0)
    meta = state.get("meta") or {}
    unresolved = int(meta.get("unresolved_rounds", 0) or 0)

    if intent == "human":
        return True, "用户主动要求转人工"
    if intent == "complaint":
        return True, "投诉类问题需人工处理"
    if conf and conf < settings.intent_confidence_threshold:
        return True, f"意图置信度过低（{conf:.2f}），为避免答非所问转人工"
    if unresolved >= settings.unresolved_rounds_threshold:
        return True, f"连续 {unresolved} 轮未能解决"
    return False, ""


def _extract_params(text: str) -> dict:
    order = _ORDER_NO_RE.search(text)
    phone = _PHONE_RE.search(text)
    return {"order_no": order.group(0) if order else "", "phone": phone.group(0) if phone else ""}


async def tool_call_node(
    state: ChatState,
    human_tool: HumanHandoffTool,
    order_tool: OrderQueryTool,
    refund_tool: RefundTool,
) -> ChatState:
    text = state.get("user_input", "")
    intent = state.get("intent", "other")

    need_human, reason = _should_transfer(state)
    if need_human:
        transcript = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in (state.get("history") or [])
        ]
        transcript.append({"role": "user", "content": text})
        result = await human_tool.run(
            session_id=state.get("session_id", ""),
            user_input=text,
            intent=intent,
            confidence=state.get("intent_confidence", 0.0),
            summary=state.get("intent_reason", ""),
            transcript=transcript,
            user_id=state.get("user_id"),
        )
        # 从结果文本中提取工单号，供前端/落库使用
        ticket_no = ""
        _m = re.search(r"(TK[A-Z0-9]{14})", result)
        if _m:
            ticket_no = _m.group(1)
        return {
            "need_human": True,
            "human_reason": reason,
            "tool_name": "human_handoff",
            "tool_result": result,
            "answer": result,
            "ticket_no": ticket_no,
        }

    params = _extract_params(text)
    if intent == "query_order":
        result = await order_tool.run(**params)
        return {"tool_name": "query_order", "tool_result": result, "tool_args": params}
    if intent == "refund":
        result = await refund_tool.run(order_no=params.get("order_no", ""), reason=text)
        return {"tool_name": "apply_refund", "tool_result": result, "tool_args": params}

    return {"tool_name": "", "tool_result": ""}
