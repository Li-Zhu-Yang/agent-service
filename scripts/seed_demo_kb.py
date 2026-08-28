"""注入演示知识库（一家虚拟「智享电器」的客服资料）。

用法：
    python -m scripts.seed_demo_kb
    python -m scripts.seed_demo_kb --force   # 重跑时覆盖同名文档
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from core.database import SessionLocal, init_db  # noqa: E402
from models.document import Document  # noqa: E402
from rag.ingestion.pipeline import ingest_text  # noqa: E402

DEMO_DOCS: dict[str, str] = {
    "售后维修服务指南": """# 售后维修服务指南

## 保修政策
问：产品保修期是多久？
答：自签收之日起，整机保修一年，核心部件（压缩机、主板）保修三年。保修期内非人为损坏免费维修。
问：哪些情况不在保修范围内？
答：人为损坏、进水、私自拆机改装、使用非官方配件导致的故障，不在保修范围内，维修需付费。

## 报修流程
问：怎么申请报修？
答：在聊天窗口回复「报修」，或拨打客服热线 400-800-1234，提供订单号和故障描述即可。我们的售后工程师会在 24 小时内联系您。
问：报修需要提供什么资料？
答：需要订单号、机器型号、购买日期和故障现象描述。若无法提供订单号，可用注册手机号查询。

## 上门维修
问：报修后多久上门？
答：城市范围内一般 48 小时内上门，偏远地区 72 小时内。上门时间可和工程师协商。
问：维修需要收费吗？
答：保修期内符合保修条件的免费；超出保修期或人为损坏按价目表收费，上门前工程师会先报价。
""",
    "退换货与退款流程": """# 退换货与退款流程

## 七天无理由退货
问：支持七天无理由退货吗？
答：支持。自签收之日起 7 天内，商品未使用、不影响二次销售，可申请无理由退货。
问：七天无理由退货由谁承担运费？
答：非质量问题退货，运费由买家承担；质量问题退货，运费由商家承担。

## 换货
问：商品有质量问题想换货怎么办？
答：签收 15 天内出现质量问题，可申请换新。在聊天中回复「换货」，提供订单号和故障照片即可。

## 退款流程
问：退款流程是怎样的？
答：申请退款 → 商家 48 小时内审核 → 审核通过后原路退回。一般到账时间：支付宝/微信 1-3 个工作日，银行卡 3-7 个工作日。
问：退款多久到账？
答：审核通过后，支付渠道原路退回，支付宝/微信 1-3 个工作日到账，银行卡 3-7 个工作日。
问：退款进度在哪查？
答：可以在「我的订单 - 退款记录」中查看，或直接询问本客服，我们会帮你查询。

## 退款注意事项
问：退款金额会和优惠券一起退回吗？
答：使用优惠券的订单退款时，优惠券按比例分摊退款，已过期的优惠券不退还。
""",
    "订单与物流查询": """# 订单与物流查询

## 订单查询
问：怎么查我的订单？
答：提供下单手机号或订单号，客服可为您查询订单状态。订单状态包括：待付款、待发货、已发货、已完成。
问：下单后多久发货？
答：现货商品 48 小时内发货，预售商品按页面标注的发货时间发货。

## 物流跟踪
问：快递到哪了？
答：请提供订单号，我们会为您查询最新物流轨迹。
问：物流显示签收但我没收到货怎么办？
答：请先确认是否由家人或物业代收。若确认未收到，我们会在 24 小时内联系物流核实并尽快补发或退款。
""",
    "发票与优惠券": """# 发票与优惠券

## 发票
问：怎么开发票？
答：在「我的订单」中选择订单申请开具电子发票，填写抬头和邮箱，1-3 个工作日发送至邮箱。
问：支持开具增值税专用发票吗？
答：支持。企业客户可在下单时选择专票，需提供纳税人识别号、开户行等开票信息。

## 优惠券
问：优惠券怎么使用？
答：下单结算时选择可用的优惠券即可自动抵扣。一张订单只能使用一张优惠券。
问：优惠券过期了能补发吗？
答：过期优惠券不补发，请留意使用有效期。新品上市和节假日我们会推送新券。
""",
    "会员与常见问题": """# 会员与常见问题

## 会员权益
问：会员有什么权益？
答：注册即享积分累计、生日礼、专属客服和会员价商品。消费 1 元积 1 分，积分可抵现。

## 联系人工客服
问：怎么转人工客服？
答：直接说「转人工」或「人工客服」，系统会自动为您转接。工作时间 9:00-21:00。
问：人工客服服务时间是几点？
答：人工客服服务时间为每天 9:00-21:00，其他时段可留言，我们会在次日优先处理。

## 其他
问：你们的客服电话是多少？
答：客服热线 400-800-1234，服务时间 9:00-21:00。
""",
}


async def _run(force: bool = False) -> None:
    init_db()
    with SessionLocal() as db:
        for title, text in DEMO_DOCS.items():
            existing = db.scalar(select(Document).where(Document.title == title))
            if existing and not force:
                print(f"  [跳过] {title}（已存在，加 --force 覆盖）")
                continue
            doc_id = existing.doc_id if existing else None
            from rag.ingestion.pipeline import new_doc_id

            doc_id = doc_id or new_doc_id()
            stats = await ingest_text(doc_id=doc_id, title=title, text=text, source=f"{title}.md", category="演示知识库")
            if existing:
                existing.status = "ready"
                existing.chunk_count = stats["chunk_count"]
                existing.content_length = stats["char_count"]
                existing.error = ""
            else:
                db.add(
                    Document(
                        doc_id=doc_id,
                        title=title,
                        source=f"{title}.md",
                        file_type="md",
                        status="ready",
                        chunk_count=stats["chunk_count"],
                        content_length=stats["char_count"],
                        category="演示知识库",
                    )
                )
            print(f"  [入库] {title}: {stats['chunk_count']} 块 / {stats['char_count']} 字")
        db.commit()
    print("[seed_demo_kb] 完成")


def main() -> None:
    asyncio.run(_run(force="--force" in sys.argv))


if __name__ == "__main__":
    main()
