"""回复生成逻辑（纯逻辑层，供 LangGraph response 节点调用）。

- 转人工 / 问候 / 高频缓存 / 知识缺失 / 无 LLM 兜底：由 fallback_answer 判定并返回答案。
- 需要 LLM 时返回 None，由节点负责逐 token 流式生成。
"""
from __future__ import annotations

import re
from typing import Any

from core.llm_client import get_llm_client
from core.redis_client import cache

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


def cache_key(intent: str, text: str) -> str:
    return f"qa:{intent}:{_normalize(text)[:60]}"


def cacheable(intent: str, text: str) -> bool:
    # 含订单号/手机号等个人数据不缓存
    return intent in _CACHEABLE_INTENTS and not re.search(r"\d{11}", text)


def yield_text(text: str):
    """把完整文本按小块切分（用于非 LLM 路径的流式回放）。"""
    for i in range(0, len(text), _STREAM_CHUNK):
        yield text[i : i + _STREAM_CHUNK]


def build_messages(state: dict) -> tuple[str, list[dict]]:
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


async def fallback_answer(
    state: dict,
) -> tuple[str, bool, dict[str, Any]] | None:
    """返回 (answer, from_cache, meta)；返回 None 表示需走 LLM 流式生成。"""
    intent = state.get("intent", "other")
    text = state.get("user_input", "")
    need_human = state.get("need_human", False)
    meta = dict(state.get("meta") or {})
    llm = get_llm_client()

    # ---------- 转人工：回放工单结果 ----------
    if need_human:
        answer = state.get("answer") or state.get("tool_result") or (
            "已为您转接人工客服，问题专员正在处理中。"
        )
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return answer, False, meta

    # ---------- 问候：固定欢迎语 ----------
    if intent == "greeting":
        meta["unresolved_rounds"] = 0
        return GREETING_REPLY, False, meta

    # ---------- 高频问答缓存 ----------
    if cacheable(intent, text):
        cached = await cache.get(cache_key(intent, text))
        if cached:
            meta["unresolved_rounds"] = 0
            return str(cached), True, meta

    # ---------- 工具结果直接作为答案（未配置 LLM 时兜底） ----------
    if state.get("tool_result") and not llm.configured:
        meta["unresolved_rounds"] = 0
        return state["tool_result"], False, meta

    # ---------- 知识缺失 ----------
    no_knowledge = state.get("no_knowledge", False) and not state.get("tool_result")
    if no_knowledge and intent in {"other", "query_order"}:
        meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return NO_KNOWLEDGE_REPLY, False, meta

    # ---------- 未配置 LLM：有命中知识则直接回放片段 ----------
    if not llm.configured:
        docs = state.get("retrieved_docs") or []
        if docs:
            answer = docs[0].get("chunk", NO_KNOWLEDGE_REPLY)
            meta["unresolved_rounds"] = 0
        else:
            answer = NO_KNOWLEDGE_REPLY
            meta["unresolved_rounds"] = int(meta.get("unresolved_rounds", 0) or 0) + 1
        return answer, False, meta

    return None
