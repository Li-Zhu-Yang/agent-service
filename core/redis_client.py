"""缓存封装：对外统一暴露异步 `cache` 对象。

- Redis 可用时走 Redis（支持多 worker 共享、缓存、限流、会话记忆）。
- Redis 不可用（未安装 / 连接失败 / settings.redis_enabled=False）时自动降级为
  进程内内存缓存，保证本地无 Docker 也能跑通全链路。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from bootstrap.settings import settings

logger = logging.getLogger(__name__)


class BaseCache:
    """缓存抽象接口。"""

    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def incr(self, key: str, ttl: int | None = None) -> int: ...

    async def expire(self, key: str, ttl: int) -> None: ...

    async def close(self) -> None: ...

    async def ping(self, timeout: float = 1.0) -> bool:
        return True


class MemoryCache(BaseCache):
    """进程内缓存：dict + 过期时间。适用于单进程开发/测试。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _alive(self, key: str) -> bool:
        if key not in self._store:
            return False
        _, expire_at = self._store[key]
        return expire_at is None or expire_at > time.time()

    async def get(self, key: str) -> Any | None:
        if not self._alive(key):
            return None
        return self._store[key][0]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expire_at = time.time() + ttl if ttl else None
        async with self._lock:
            self._store[key] = (value, expire_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return self._alive(key)

    async def incr(self, key: str, ttl: int | None = None) -> int:
        async with self._lock:
            cur = 0 if not self._alive(key) else (self._store[key][0] or 0)
            cur += 1
            expire_at = time.time() + ttl if ttl else None
            self._store[key] = (cur, expire_at)
            return cur

    async def expire(self, key: str, ttl: int) -> None:
        if key in self._store:
            self._store[key] = (self._store[key][0], time.time() + ttl)

    async def close(self) -> None:
        self._store.clear()


class RedisCache(BaseCache):
    """Redis 缓存（redis.asyncio）。值做 JSON 序列化。"""

    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis

        self._redis: Redis = Redis.from_url(url, decode_responses=True)

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode(raw: str | None) -> Any | None:
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw

    async def ping(self, timeout: float = 2.0) -> bool:
        try:
            return bool(await asyncio.wait_for(self._redis.ping(), timeout=timeout))
        except Exception:
            return False

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        return self._decode(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._redis.set(key, self._encode(value), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def incr(self, key: str, ttl: int | None = None) -> int:
        val = await self._redis.incr(key)
        if ttl:
            await self._redis.expire(key, ttl)
        return int(val)

    async def expire(self, key: str, ttl: int) -> None:
        await self._redis.expire(key, ttl)

    async def close(self) -> None:
        await self._redis.aclose()


class CacheProxy(BaseCache):
    """惰性初始化 + 故障降级的缓存门面。"""

    def __init__(self) -> None:
        self._impl: BaseCache | None = None

    async def _resolve(self) -> BaseCache:
        if self._impl is not None:
            return self._impl
        impl: BaseCache
        if not settings.redis_enabled:
            logger.info("缓存: settings.redis_enabled=False，使用内存缓存")
            impl = MemoryCache()
        else:
            try:
                rc = RedisCache(settings.redis_url)
                if await rc.ping(timeout=2):
                    logger.info("缓存: Redis 已连接 %s", settings.redis_url)
                    impl = rc
                else:
                    logger.warning("缓存: Redis 连接失败，降级为内存缓存")
                    impl = MemoryCache()
            except Exception as exc:  # redis 未安装等
                logger.warning("缓存: Redis 不可用(%s)，降级为内存缓存", exc)
                impl = MemoryCache()
        self._impl = impl
        return impl

    async def get(self, key: str) -> Any | None:
        return await (await self._resolve()).get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await (await self._resolve()).set(key, value, ttl)

    async def delete(self, key: str) -> None:
        await (await self._resolve()).delete(key)

    async def exists(self, key: str) -> bool:
        return await (await self._resolve()).exists(key)

    async def incr(self, key: str, ttl: int | None = None) -> int:
        return await (await self._resolve()).incr(key, ttl)

    async def expire(self, key: str, ttl: int) -> None:
        await (await self._resolve()).expire(key, ttl)

    async def close(self) -> None:
        if self._impl is not None:
            await self._impl.close()


# 全局单例
cache = CacheProxy()
