"""对话状态定义（LangGraph State）。

字段说明：
- user_input / history     当前输入与近几轮上下文
- intent / confidence       意图识别结果
- retrieved_docs            知识检索结果
- tool_*                    工具调用所需
- need_human / human_reason 是否转人工及原因
- answer / meta              最终回复与过程元数据
"""
from __future__ import annotations

from typing import Any, TypedDict


class ChatState(TypedDict, total=False):
    session_id: str
    user_id: int | None
    user_input: str

    # 意图
    intent: str
    intent_confidence: float
    intent_reason: str

    # 历史（[{role, content}]）
    history: list[dict[str, str]]
    # 历史意图序列（由近到远）
    history_intents: list[str]

    # 检索
    retrieved_docs: list[dict[str, Any]]
    no_knowledge: bool

    # 工具
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: str

    # 分流
    need_human: bool
    human_reason: str
    ticket_no: str

    # 回复
    answer: str
    from_cache: bool
    meta: dict[str, Any]


def initial_state(
    session_id: str,
    user_input: str,
    user_id: int | None = None,
    history: list[dict[str, str]] | None = None,
    meta: dict[str, Any] | None = None,
) -> ChatState:
    """构造初始状态。"""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_input": user_input.strip(),
        "intent": "",
        "intent_confidence": 0.0,
        "intent_reason": "",
        "history": history or [],
        "history_intents": [],
        "retrieved_docs": [],
        "no_knowledge": False,
        "tool_name": "",
        "tool_args": {},
        "tool_result": "",
        "need_human": False,
        "human_reason": "",
        "ticket_no": "",
        "answer": "",
        "from_cache": False,
        "meta": meta or {"unresolved_rounds": 0},
    }
