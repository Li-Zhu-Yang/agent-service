"""限流器：按 key（IP / 用户）做固定窗口计数，窗口滑动。

- Redis 可用时用 Redis INCR + EXPIRE，多 worker 一致；
- 内存降级时同样基于统一 cache 门面（MemoryCache 的 INCR 语义一致）。
"""
from __future__ import annotations

from bootstrap.settings import settings
from core.redis_client import cache


class RateLimiter:
    def __init__(self, limit: int | None = None, window_seconds: int = 60) -> None:
        self.limit = limit if limit is not None else settings.rate_limit_per_minute
        self.window = window_seconds

    async def allow(self, key: str) -> tuple[bool, int]:
        """返回 (是否放行, 当前窗口已用次数)。"""
        if self.limit <= 0:
            return True, 0
        count = await cache.incr(f"rl:{key}", ttl=self.window)
        return count <= self.limit, count

    async def reset(self, key: str) -> None:
        await cache.delete(f"rl:{key}")


# 全局单例
rate_limiter = RateLimiter()
