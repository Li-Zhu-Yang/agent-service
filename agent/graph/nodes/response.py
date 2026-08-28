"""最终回复节点：整合意图 / 知识 / 工具结果，流式生成回答。

- 转人工：直接流式回放工单结果（不调用 LLM）。
- 问候：使用固定欢迎语（低延迟）。
- 高频问答缓存：命中直接回放缓存，跳过 LLM。
- 知识类问题：组装 Prompt 交给 LLM 流式生成；未配置 LLM 时直接返回工具/检索结果。

LangGraph 流式约定：节点是普通 async 函数，通过 `langgraph.config.get_stream_writer()`
把 token 以 custom event 发出；return 的值作为本轮状态更新。
（Python 语法禁止 generator/async generator 带 return 值，故不能把节点写成 generator。）
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from langgraph.config import get_stream_writer

from agent.graph.state import ChatState
from bootstrap.settings import settings
from core.llm_client import get_llm_client
from core.redis_client import cache

logger = logging.getLogger(__name__)

GREETING_REPLY = (
    "您好，我是智享电器的智能客服，很高兴为您服务！您可以问我：\n"
    "- 订单/物流查询\n- 退款/退货\n- 报修/维修\n- 发票/优惠券\n"
    "也可以直接说「转人工」联系人工客服。"
)

NO_KNOWLEDGE_REPLY = (
    "抱歉，这个问题我暂时没有在知识库中找到准确答案，怕回答错误误导您。"
    "您可以换个说法再问一次，或者直接说「转人工」，我会把您的问题同步给人工客服专员处理。"
)

_STREAM_CHUNK = 10  # 非 LLM 回放时的按字切块大小
_NORMALIZE_RE = re.compile(r"[\W_]+")
_CACHEABLE_INTENTS = {"refund", "after_sales", "invoice", "coupon", "member", "repair"}


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.lower())


def _cache_key(intent: str, text: str) -> str:
    return f"qa:{intent}:{_normalize(text)[:60]}"


def _cacheable(intent: str, text: str) -> bool:
    # 含订单号/手机号等个人数据不缓存
    return intent in _CACHEABLE_INTENTS and not re.search(r"\d{11}", text)


def _yield_text(text: str):
    """把完整文本按小块切分（用于非 LLM 路径的流式回放）。"""
    for i in range(0, len(text), _STREAM_CHUNK):
        yield text[i : i + _STREAM_CHUNK]


def _build_messages(state: ChatState) -> tuple[str, list[dict]]:
    """构造 system + messages。"""
    intent = state.get("intent", "other")
    docs = state.get("retrieved_docs") or []
    tool_result = state.get("tool_result", "")

    knowledge_block = "\n\n".join(
        f"【{d.get('title','')}】\n{d.get('chunk','')}" for d in docs[:4]
    )
    system_lines = [
        "你是「智享电器」官方智能客服。请用简体中文、口语化、热情地回答问题。",
        "回答要求：",
        "1. 优先依据下方【知识库内容】作答，不要编造知识库中没有的信息；",
        "2. 若知识库没有相关内容，直接说明不清楚，并建议用户换个说法或转人工；",
        "3. 涉及订单/退款等操作类问题，如【工具结果】已给出，直接转达工具结果；",
        "4. 回复保持简洁（一般不超过 200 字），可适当分点。",
    ]
    if knowledge_block:
        system_lines.append(f"【知识库内容】\n{knowledge_block}")
    if tool_result:
        system_lines.append(f"【工具结果】\n{tool_result}")
    system = "\n".join(system_lines)

    messages: list[dict] = []
    for m in (state.get("history") or [])[-4:]:
        messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    messages.append({"role": "user", "content": state.get("user_input", "")})
    return system, messages


async def response_node(state: ChatState):
    """流式回复节点：writer 发送 token（custom events），return 状态更新。"""
    writer = get_stream_writer()
    intent = state.get("intent", "other")
    text = state.get("user_input", "")
    need_human = state.get("need_human", False)
    meta = dict(state.get("meta") or {})

    # ---------- 转人工：回放工单结果 ----------
    if need_human:
        answer = state.get("answer") or state.get("tool_result") or (
            "已为您转接人工客服，问题专员正在处理中。"
        )
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return {"answer": answer, "from_cache": False, "meta": meta}

    # ---------- 问候：固定欢迎语 ----------
    if intent == "greeting":
        answer = GREETING_REPLY
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = 0
        return {"answer": answer, "from_cache": False, "meta": meta}

    # ---------- 高频问答缓存 ----------
    cache_key = None
    cached: str | None = None
    if _cacheable(intent, text):
        cache_key = _cache_key(intent, text)
        cached = await cache.get(cache_key)
    if cached:
        answer = str(cached)
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = 0
        return {"answer": answer, "from_cache": True, "meta": meta}

    # ---------- 工具结果直接作为答案（未配置 LLM 时兜底） ----------
    llm = get_llm_client()
    if state.get("tool_result") and not llm.configured:
        answer = state["tool_result"]
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = 0
        return {"answer": answer, "from_cache": False, "meta": meta}

    # ---------- 知识缺失 ----------
    no_knowledge = state.get("no_knowledge", False) and not state.get("tool_result")
    if no_knowledge and intent in {"other", "query_order"}:
        answer = NO_KNOWLEDGE_REPLY
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return {"answer": answer, "from_cache": False, "meta": meta}

    # ---------- LLM 流式生成 ----------
    if not llm.configured:
        # 未配置 LLM：有命中知识则直接回放片段，保证离线也能答知识类问题
        docs = state.get("retrieved_docs") or []
        if docs:
            answer = docs[0].get("chunk", NO_KNOWLEDGE_REPLY)
            meta["unresolved_rounds"] = 0
        else:
            answer = NO_KNOWLEDGE_REPLY
            meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        for _c in _yield_text(answer):
            writer(_c)
        return {"answer": answer, "from_cache": False, "meta": meta}

    system, messages = _build_messages(state)
    started = time.perf_counter()
    parts: list[str] = []
    try:
        async for token in llm.stream(system=system, messages=messages):
            parts.append(token)
            writer(token)
    except Exception as exc:
        logger.error("回复生成失败: %s", exc)
        answer = "抱歉，回复生成出现异常，请稍后再试，或直接说「转人工」。"
        for _c in _yield_text(answer):
            writer(_c)
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return {"answer": answer, "from_cache": False, "meta": meta}

    answer = "".join(parts).strip()
    latency_ms = int((time.perf_counter() - started) * 1000)
    meta["unresolved_rounds"] = 0
    meta["latency_ms"] = latency_ms
    meta["tokens_used"] = max(1, len(answer) // 2)

    if cache_key:
        await cache.set(cache_key, answer, ttl=settings.qa_cache_ttl)

    return {"answer": answer, "from_cache": False, "meta": meta}
