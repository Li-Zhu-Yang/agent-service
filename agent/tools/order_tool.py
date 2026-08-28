"""订单查询工具。

演示实现：无真实 ERP 时返回确定性 mock 数据；接入真实订单系统时替换本类即可。
"""
from __future__ import annotations

import hashlib

from agent.tools.base import BaseTool, ToolParam, ToolSpec


class OrderQueryTool(BaseTool):
    spec = ToolSpec(
        name="query_order",
        description="根据订单号或手机号查询订单状态、物流信息",
        parameters=[
            ToolParam("order_no", "string", "订单号（11位数字）", required=False),
            ToolParam("phone", "string", "下单手机号", required=False),
        ],
    )

    async def run(self, order_no: str = "", phone: str = "") -> str:
        key = order_no or phone or "anonymous"
        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        statuses = ["已发货", "已发货", "待发货", "已完成", "待付款"]
        status = statuses[h % len(statuses)]
        address_city = ["上海", "北京", "广州", "杭州", "成都"][h % 5]
        if order_no:
            return (
                f"订单 {order_no} 当前状态：{status}。"
                + (f"商品正在派往{address_city}，预计 2 天内送达。" if status == "已发货" else "")
            )
        if phone:
            return f"尾号 {phone[-4:]} 的账号下共有 3 个有效订单，最近一笔状态：{status}。"
        return "请提供订单号或手机号以便查询。"
