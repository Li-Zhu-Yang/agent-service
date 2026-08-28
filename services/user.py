"""用户管理：创建 / 查询。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions import AppError
from models.user import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "user",
    display_name: str = "",
) -> User:
    if get_user_by_username(db, username):
        raise AppError("用户名已存在")
    user = User(username=username, role=role, display_name=display_name or username, is_active=True)
    user.set_password(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, keyword: str = "", limit: int = 50) -> list[User]:
    stmt = select(User).order_by(User.id.desc()).limit(limit)
    if keyword:
        stmt = stmt.where(User.username.contains(keyword))
    return list(db.scalars(stmt))
