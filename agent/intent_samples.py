"""意图识别小样本池（few-shot）。

这些「问题→意图」样本用于两处：
1. 运行时注入 LLM 提示词做零样本 few-shot 分类；
2. scripts/export_intent_samples.py 导出为训练集（JSONL），供后续接入 PEFT 微调
   （docs/意图标注指南.md 说明了如何扩充样本）。

维护方式：在下方追加 ("用户问法", "意图")，意图取值见 INTENTS。
"""
from __future__ import annotations

# 意图中文说明（用于提示词与报表展示）
INTENT_LABELS: dict[str, str] = {
    "greeting": "问候/寒暄",
    "query_order": "查询订单/物流",
    "refund": "退款/退货",
    "repair": "报修/维修",
    "complaint": "投诉",
    "after_sales": "售后/质保/换货",
    "invoice": "发票",
    "coupon": "优惠券",
    "member": "会员/账号",
    "human": "转人工客服",
    "other": "其他",
}

# 意图 → 触发关键词（规则快速命中，低延迟兜底）
RULE_KEYWORDS: dict[str, list[str]] = {
    "human": ["转人工", "人工客服", "接人工", "真人客服", "人工", "投诉专员", "找客服"],
    "repair": ["报修", "维修", "保修", "检修", "上门修", "坏了", "故障", "损坏", "不工作了", "无法开机"],
    "refund": ["退款", "退货", "退钱", "七天无理由", "退换货", "退货退款"],
    "query_order": ["订单", "物流", "快递", "发货", "查单", "签收", "到哪了", "配送"],
    "complaint": ["投诉", "举报", "差评", "态度差", "气死", "投诉电话"],
    "after_sales": ["售后", "质保", "三包", "换新", "换货", "以旧换新", "维修点"],
    "invoice": ["发票", "开票", "专票", "普票", "税号", "电子发票"],
    "coupon": ["优惠券", "满减", "折扣", "代金券", "领券", "用券"],
    "member": ["会员", "积分", "注册", "登录", "账号", "密码", "绑定", "实名"],
    "greeting": ["你好", "您好", "hi", "hello", "在吗", "早上好", "下午好", "晚上好"],
}

# few-shot 示例（小样本池，按意图均衡）
INTENT_SAMPLES: list[tuple[str, str]] = [
    ("你好", "greeting"),
    ("在吗", "greeting"),
    ("我想查一下我的订单", "query_order"),
    ("快递到哪里了", "query_order"),
    ("我的货什么时候发货", "query_order"),
    ("怎么查物流", "query_order"),
    ("我要退货", "refund"),
    ("订单怎么退款", "refund"),
    ("支持七天无理由退货吗", "refund"),
    ("退款多久到账", "refund"),
    ("我的冰箱坏了要报修", "repair"),
    ("洗衣机不工作了", "repair"),
    ("怎么申请维修", "repair"),
    ("保修期内维修收费吗", "repair"),
    ("我要投诉你们的客服", "complaint"),
    ("服务态度太差了", "complaint"),
    ("售后质保怎么算", "after_sales"),
    ("可以换新吗", "after_sales"),
    ("怎么开发票", "invoice"),
    ("能开增值税专用发票吗", "invoice"),
    ("优惠券怎么用", "coupon"),
    ("有满减券吗", "coupon"),
    ("会员有什么权益", "member"),
    ("怎么注册账号", "member"),
    ("转人工客服", "human"),
    ("帮我联系人工", "human"),
    ("你们营业时间几点", "other"),
]
