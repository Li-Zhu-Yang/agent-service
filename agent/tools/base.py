"""工具基类：统一 spec 描述 + run 接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ToolParam:
    def __init__(self, name: str, ptype: str, description: str, required: bool = True):
        self.name = name
        self.type = ptype
        self.description = description
        self.required = required


class ToolSpec:
    def __init__(self, name: str, description: str, parameters: list[ToolParam]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_mcp_input_schema(self) -> dict:
        props = {
            p.name: {"type": p.type, "description": p.description}
            for p in self.parameters
        }
        required = [p.name for p in self.parameters if p.required]
        return {"type": "object", "properties": props, "required": required}


class BaseTool(ABC):
    spec: ToolSpec

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """执行工具，返回文本结果。"""
