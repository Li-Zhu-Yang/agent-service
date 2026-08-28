"""长期记忆：用户画像（意图分布、咨询主题、总量），从消息表聚合。

用于个性化应答与运营报表（哪些用户反复咨询同一类问题）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.conversation import Conversation
from models.message import Message


def get_user_profile(db: Session, user_id: int) -> dict[str, Any]:
    """统计用户历史：意图分布、总轮数、最近咨询主题。"""
    conv_ids = select(Conversation.id).where(Conversation.user_id == user_id)
    rows = (
        db.execute(
            select(Message.intent, func.count(Message.id)).where(
                Message.conversation_id.in_(conv_ids), Message.role == "assistant"
            ).group_by(Message.intent)
        ).all()
    )
    intent_dist = {intent or "other": count for intent, count in rows}
    total_turns = sum(intent_dist.values())
    recent_msgs = (
        db.execute(
            select(Message.content)
            .where(Message.conversation_id.in_(conv_ids), Message.role == "user")
            .order_by(Message.id.desc())
            .limit(5)
        ).scalars().all()
    )
    return {
        "user_id": user_id,
        "total_turns": total_turns,
        "intent_distribution": intent_dist,
        "recent_topics": list(reversed(recent_msgs)),
    }
