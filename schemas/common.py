"""通用响应结构。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: str = "ok"
    message: str = "success"
    data: T | None = None
