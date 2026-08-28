"""初始化数据库。

用法：
    python -m scripts.init_db          # 建表（开发快速开始）
    python -m scripts.init_db --drop   # 先删表再重建（慎用）
"""
from __future__ import annotations

import sys

from core.database import engine, init_db
from models.base import Base
import models  # noqa: F401


def main() -> None:
    if "--drop" in sys.argv:
        print("[init_db] 删除全部数据表...")
        Base.metadata.drop_all(bind=engine)
    init_db()
    print(f"[init_db] 建表完成 -> {engine.url!s}")


if __name__ == "__main__":
    main()
