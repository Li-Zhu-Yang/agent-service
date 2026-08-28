"""退款处理工具：提交退款申请（演示实现，返回处理结果）。"""
from __future__ import annotations

from agent.tools.base import BaseTool, ToolParam, ToolSpec


class RefundTool(BaseTool):
    spec = ToolSpec(
        name="apply_refund",
        description="为订单提交退款/退货申请",
        parameters=[
            ToolParam("order_no", "string", "订单号"),
            ToolParam("reason", "string", "退款原因", required=False),
        ],
    )

    async def run(self, order_no: str = "", reason: str = "用户主动申请") -> str:
        if not order_no:
            return "请提供订单号才能发起退款申请。"
        return (
            f"已为订单 {order_no} 提交退款申请（原因：{reason or '未填写'}）。"
            "商家将在 48 小时内审核，审核通过后款项原路退回，一般 1-3 个工作日到账。"
        )
