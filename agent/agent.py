"""Agent 门面：统一封装 LangGraph 工作流的调用。

- answer()          非流式：跑完整流程，返回最终状态（供测试 / MCP / 桌面版）。
- stream()          流式：yield LLM 增量 token（供网页 SSE）。
- stream_state()    流式同时返回最终状态（供 chat 路由落库）。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from agent.graph.graph_builder import get_graph
from agent.graph.state import ChatState, initial_state
from agent.memory import short_term

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self) -> None:
        self.graph = get_graph()

    def _make_state(
        self,
        session_id: str,
        user_input: str,
        user_id: int | None,
        history: list[dict[str, str]] | None,
        history_intents: list[str] | None,
        meta: dict[str, Any] | None,
    ) -> ChatState:
        return initial_state(
            session_id=session_id,
            user_input=user_input,
            user_id=user_id,
            history=history,
            meta=meta,
        ) | {"history_intents": history_intents or []}

    async def answer(
        self,
        session_id: str,
        user_input: str,
        user_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        history_intents: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ChatState:
        """非流式执行，返回最终状态。"""
        state = self._make_state(session_id, user_input, user_id, history, history_intents, meta)
        return await self.graph.ainvoke(state)

    async def stream(
        self,
        session_id: str,
        user_input: str,
        user_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        history_intents: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """只 yield 最终回复的 token。"""
        state = self._make_state(session_id, user_input, user_id, history, history_intents, meta)
        async for mode, payload in self.graph.astream(state, stream_mode=["custom", "updates"]):
            if mode == "custom":
                yield str(payload)

    async def stream_state(
        self,
        session_id: str,
        user_input: str,
        user_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        history_intents: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """yield (mode, payload)：custom 为 token，updates 为节点状态增量。"""
        state = self._make_state(session_id, user_input, user_id, history, history_intents, meta)
        async for mode, payload in self.graph.astream(state, stream_mode=["custom", "updates"]):
            yield mode, payload


# 供网页/MCP 复用的会话上下文加载
async def load_context(session_id: str) -> tuple[list[dict[str, str]], list[str], dict[str, Any]]:
    """从短期记忆加载 (history, history_intents, meta)。"""
    history = await short_term.get_history(session_id, limit=10)
    meta = await short_term.get_meta(session_id)
    history_intents = meta.get("intents", []) or []
    return history, history_intents, meta


async def save_context(
    session_id: str,
    user_input: str,
    assistant_answer: str,
    assistant_meta: dict[str, Any],
) -> None:
    """更新短期记忆（写入本轮问答与意图序列）。"""
    intents = (await short_term.get_meta(session_id)).get("intents", []) or []
    if assistant_meta.get("intent"):
        intents = (intents + [assistant_meta["intent"]])[-8:]
    await short_term.append_turn(
        session_id,
        user_input,
        assistant_answer,
        assistant_meta={**assistant_meta, "intents": intents},
    )


agent = Agent()
