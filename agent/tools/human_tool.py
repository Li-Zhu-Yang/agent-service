"""转人工工具：创建工单（Ticket），同步对话记录与问题详情。"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from agent.tools.base import BaseTool, ToolParam, ToolSpec

logger = logging.getLogger(__name__)


def _new_ticket_no() -> str:
    return "TK" + dt.datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:6].upper()


class HumanHandoffTool(BaseTool):
    """创建转人工工单。构造时传入会话工厂（如 core.database.SessionLocal）。"""

    spec = ToolSpec(
        name="human_handoff",
        description="转接人工客服并创建问题工单，同步用户对话记录",
        parameters=[
            ToolParam("session_id", "string", "会话 ID"),
            ToolParam("user_input", "string", "用户最新问题"),
            ToolParam("intent", "string", "识别到的意图", required=False),
            ToolParam("confidence", "number", "意图置信度", required=False),
            ToolParam("summary", "string", "问题摘要", required=False),
        ],
    )

    def __init__(self, session_factory=None) -> None:
        self.session_factory = session_factory

    async def run(
        self,
        session_id: str = "",
        user_input: str = "",
        intent: str = "",
        confidence: float = 0.0,
        summary: str = "",
        transcript: list[dict] | None = None,
        user_id: int | None = None,
    ) -> str:
        ticket_no = _new_ticket_no()
        try:
            if self.session_factory is not None:
                from models.ticket import Ticket

                db = self.session_factory()
                try:
                    db.add(
                        Ticket(
                            ticket_no=ticket_no,
                            session_id=session_id,
                            user_id=user_id,
                            customer_text=user_input,
                            issue_summary=summary or user_input,
                            intent=intent,
                            confidence=float(confidence or 0.0),
                            priority="high" if intent == "complaint" else "normal",
                            status="open",
                            transcript=transcript or [],
                        )
                    )
                    db.commit()
                except Exception as exc:  # 工单落库失败不阻断转人工
                    logger.error("创建工单失败: %s", exc)
                    db.rollback()
                finally:
                    db.close()
        except Exception as exc:
            logger.warning("转人工工具异常（仍继续转接）: %s", exc)

        return (
            f"已为您转接人工客服，工单号 {ticket_no}。"
            "您的对话记录与问题详情已同步给人工专员，请稍候（工作时间 9:00-21:00）。"
        )
