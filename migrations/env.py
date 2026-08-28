"""Alembic 环境：从项目 .env 读取 DATABASE_URL，绑定到 ORM 元数据。

用法（在项目根目录执行）：
  alembic revision --autogenerate -m "xxx"   # 生成迁移
  alembic upgrade head                       # 应用迁移
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from bootstrap.settings import settings
from models.base import Base
import models  # noqa: F401  确保全部模型注册到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 注入 DATABASE_URL 与脚本搜索路径
config.set_main_option("sqlalchemy.url", settings.database_url)
if not config.get_main_option("prepend_sys_path"):
    config.set_main_option("prepend_sys_path", ".")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
