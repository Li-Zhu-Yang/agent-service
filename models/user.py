"""用户表：支持客服用户与运营管理员（JWT 认证）。"""
from __future__ import annotations

import secrets
from datetime import datetime

import hashlib
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """PBKDF2-SHA256 哈希密码，返回 (hash, salt)。纯标准库，无 C 扩展依赖。"""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000
    ).hex()
    return digest, salt


def verify_password(password: str, digest: str, salt: str) -> bool:
    check, _ = hash_password(password, salt)
    return secrets.compare_digest(check, digest)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)  # admin | user
    display_name: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash, self.password_salt = hash_password(password)

    def check_password(self, password: str) -> bool:
        return verify_password(password, self.password_hash, self.password_salt)
