"""最终回复节点：整合意图 / 知识 / 工具结果，流式生成回答。

判定与文案逻辑见 agent.generation；本节点只负责流式输出（writer 发 token）。

LangGraph 流式约定：节点是普通 async 函数，通过 `langgraph.config.get_stream_writer()`
把 token 以 custom event 发出；return 的值作为本轮状态更新。
"""
from __future__ import annotations

import logging
import time

from langgraph.config import get_stream_writer

from agent.generation import build_messages, cache_key, cacheable, fallback_answer, yield_text
from agent.graph.state import ChatState
from bootstrap.settings import settings
from core.llm_client import get_llm_client
from core.redis_client import cache

logger = logging.getLogger(__name__)

_ERROR_REPLY = "抱歉，回复生成出现异常，请稍后再试，或直接说「转人工」。"


async def response_node(state: ChatState):
    """流式回复节点：writer 发送 token（custom events），return 状态更新。"""
    writer = get_stream_writer()

    # 非 LLM 路径（转人工/问候/缓存/知识兜底）直接回放
    fallback = await fallback_answer(state)
    if fallback is not None:
        answer, from_cache, meta = fallback
        for _c in yield_text(answer):
            writer(_c)
        return {"answer": answer, "from_cache": from_cache, "meta": meta}

    # ---------- LLM 流式生成 ----------
    llm = get_llm_client()
    system, messages = build_messages(state)
    started = time.perf_counter()
    parts: list[str] = []
    meta = dict(state.get("meta") or {})
    try:
        async for token in llm.stream(system=system, messages=messages):
            parts.append(token)
            writer(token)
    except Exception as exc:
        logger.error("回复生成失败: %s", exc)
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        for _c in yield_text(_ERROR_REPLY):
            writer(_c)
        return {"answer": _ERROR_REPLY, "from_cache": False, "meta": meta}

    answer = "".join(parts).strip()
    latency_ms = int((time.perf_counter() - started) * 1000)
    meta["unresolved_rounds"] = 0
    meta["latency_ms"] = latency_ms
    meta["tokens_used"] = max(1, len(answer) // 2)

    intent = state.get("intent", "other")
    text = state.get("user_input", "")
    if cacheable(intent, text):
        await cache.set(cache_key(intent, text), answer, ttl=settings.qa_cache_ttl)

    return {"answer": answer, "from_cache": False, "meta": meta}
