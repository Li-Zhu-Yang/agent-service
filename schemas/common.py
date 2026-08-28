"""通用响应结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: str = "ok"
    message: str = "success"
    data: T | None = None


class Page(BaseModel):
    total: int = 0
    items: list[Any] = []
