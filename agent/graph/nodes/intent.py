"""意图识别节点：规则快速命中 → LLM few-shot 兜底 → 低置信标记。"""
from __future__ import annotations

from agent.graph.state import ChatState
from agent.intent import classify_intent


async def intent_node(state: ChatState) -> ChatState:
    text = state.get("user_input", "")
    history_intents = state.get("history_intents", []) or []
    result = await classify_intent(text, history_intents)

    meta = dict(state.get("meta") or {})
    confidence = result["confidence"]
    # 低置信且非规则强命中：标记为需澄清，后续可转人工或追问
    if confidence < 0.4:
        meta["needs_clarification"] = True

    return {
        "intent": result["intent"],
        "intent_confidence": confidence,
        "intent_reason": result["reason"],
        "meta": meta,
    }
