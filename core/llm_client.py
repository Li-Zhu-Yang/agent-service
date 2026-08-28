"""大模型客户端：DeepSeek / 任意 OpenAI 兼容服务（async）。

提供：
- generate()            非流式生成
- stream()              流式生成（async generator，逐 token 产出）
- complete_json()       要求模型返回 JSON 的辅助方法
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

from openai import AsyncOpenAI

from bootstrap.settings import settings
from core.exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self._client: AsyncOpenAI | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _client_sync(self):
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def _require_key(self) -> None:
        if not self.configured:
            raise LLMError(
                "尚未配置大模型 API Key：请在 .env 中填写 LLM_API_KEY"
                "（或设置 LLM_BASE_URL / LLM_MODEL 指向其他 OpenAI 兼容服务）"
            )

    def _messages(self, system: str, messages: list[dict]) -> list[dict]:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        return msgs

    async def generate(
        self,
        system: str = "",
        messages: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        self._require_key()
        try:
            resp = await self._client_sync().chat.completions.create(
                model=self.model,
                messages=self._messages(system, messages or []),
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM generate 失败: %s", exc)
            raise LLMError(f"大模型调用失败: {exc}") from exc

    async def stream(
        self,
        system: str = "",
        messages: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """逐 token 产出文本。"""
        self._require_key()
        try:
            stream = await self._client_sync().chat.completions.create(
                model=self.model,
                messages=self._messages(system, messages or []),
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.error("LLM stream 失败: %s", exc)
            raise LLMError(f"大模型流式调用失败: {exc}") from exc

    async def complete_json(
        self,
        system: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> dict:
        """要求模型返回 JSON 对象；解析失败时抛出 LLMError。"""
        raw = await self.generate(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens or 800,
            temperature=0.0,
        )
        raw = raw.strip()
        # 去掉可能的 ```json 围栏
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 兜底：截取第一对花括号
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise LLMError(f"模型返回非 JSON 内容: {raw[:200]}")


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient()
