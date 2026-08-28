"""数据模型包。导入全部模型以注册到 Base.metadata（供 Alembic / init_db 使用）。"""
from models.audit import AuditLog
from models.base import Base
from models.conversation import Conversation
from models.daily_report import DailyReport
from models.document import Document
from models.message import Message
from models.ticket import Ticket
from models.user import User

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "Conversation",
    "Message",
    "Document",
    "Ticket",
    "DailyReport",
]
