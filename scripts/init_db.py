"""初始化数据库。

用法：
    python -m scripts.init_db          # 建表（开发快速开始）
    python -m scripts.init_db --drop   # 先删表再重建（慎用）
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许以 `python -m scripts.init_db` 方式运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import engine, init_db  # noqa: E402
from models.base import Base  # noqa: E402
import models  # noqa: F401, E402


def main() -> None:
    if "--drop" in sys.argv:
        print("[init_db] 删除全部数据表...")
        Base.metadata.drop_all(bind=engine)
    init_db()
    print(f"[init_db] 建表完成 -> {engine.url!s}")


if __name__ == "__main__":
    main()
