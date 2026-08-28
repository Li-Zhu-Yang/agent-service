"""短期会话记忆：以 session_id 为键的滑动窗口上下文。

存储层统一走 core.redis_client.cache（Redis 或内存降级）。历史与数据库 message 表
双写冗余：Redis 供实时上下文，DB 供持久化与报表；Redis 缺失时回退 DB 重建。
"""
from __future__ import annotations

import logging
from typing import Any

from bootstrap.settings import settings
from core.redis_client import cache

logger = logging.getLogger(__name__)

_HIST_PREFIX = "chat:hist:"
_META_PREFIX = "chat:meta:"


def _hist_key(session_id: str) -> str:
    return f"{_HIST_PREFIX}{session_id}"


def _meta_key(session_id: str) -> str:
    return f"{_META_PREFIX}{session_id}"


async def get_history(session_id: str, limit: int | None = None) -> list[dict[str, str]]:
    """返回 [{role, content}]，最近在末尾。"""
    hist = await cache.get(_hist_key(session_id)) or []
    if limit:
        hist = hist[-limit:]
    return hist


async def append_turn(
    session_id: str, user_msg: str, assistant_msg: str, assistant_meta: dict[str, Any] | None = None
) -> None:
    """追加一轮问答，滑窗裁剪到 CONTEXT_WINDOW 对。"""
    hist = await cache.get(_hist_key(session_id)) or []
    hist.append({"role": "user", "content": user_msg})
    hist.append({"role": "assistant", "content": assistant_msg})
    max_pairs = settings.context_window
    max_msgs = max_pairs * 2
    hist = hist[-max_msgs:]
    await cache.set(_hist_key(session_id), hist, ttl=24 * 3600)
    # 会话元信息（未解决轮数等）
    meta = await cache.get(_meta_key(session_id)) or {}
    meta.update(assistant_meta or {})
    await cache.set(_meta_key(session_id), meta, ttl=24 * 3600)


async def get_meta(session_id: str) -> dict[str, Any]:
    return await cache.get(_meta_key(session_id)) or {}


async def set_meta(session_id: str, meta: dict[str, Any]) -> None:
    await cache.set(_meta_key(session_id), meta, ttl=24 * 3600)


async def clear(session_id: str) -> None:
    await cache.delete(_hist_key(session_id))
    await cache.delete(_meta_key(session_id))
