"""天气查询工具（示例外部工具：接入真实天气 API 时替换 run 实现）。"""
from __future__ import annotations

import hashlib

from agent.tools.base import BaseTool, ToolParam, ToolSpec


class WeatherTool(BaseTool):
    spec = ToolSpec(
        name="query_weather",
        description="查询某城市的天气情况（示例工具）",
        parameters=[ToolParam("city", "string", "城市名")],
    )

    async def run(self, city: str = "") -> str:
        if not city:
            return "请提供城市名。"
        h = int(hashlib.md5(city.encode()).hexdigest()[:8], 16)
        cond = ["晴", "多云", "小雨", "阴"][h % 4]
        temp = 18 + h % 15
        return f"{city}今天{cond}，气温 {temp}°C，风力 2 级。（示例数据）"
