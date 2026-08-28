"""数据库连接与会话管理（SQLAlchemy 2.0）。

默认 SQLite（开箱即用），.env 切换 PostgreSQL。
- SQLite: sqlite:///./data/ragent.db
- PostgreSQL: postgresql+psycopg://user:pass@host:port/db
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bootstrap.settings import settings
from models.base import Base

# SQLite 文件型数据库需确保父目录存在（用 make_url 解析，兼容 Windows 绝对/相对路径）
if settings.database_url.startswith("sqlite"):
    from pathlib import Path

    from sqlalchemy.engine import make_url

    _sqlite_path = Path(make_url(settings.database_url).database)
    _sqlite_path.parent.mkdir(parents=True, exist_ok=True)

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if settings.is_postgres:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
else:
    # SQLite 并发写入需此开关
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """创建全部数据表（开发环境用；生产建议走 Alembic 迁移）。"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
