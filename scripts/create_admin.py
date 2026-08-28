"""创建/更新管理员账号（读取 .env 的 ADMIN_USERNAME/ADMIN_PASSWORD）。

用法：
    python -m scripts.create_admin [username] [password]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from bootstrap.settings import settings  # noqa: E402
from core.database import SessionLocal, init_db  # noqa: E402
from models.user import User  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else settings.admin_username
    password = sys.argv[2] if len(sys.argv) > 2 else settings.admin_password

    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, role="admin", display_name="管理员", is_active=True)
            db.add(user)
            action = "创建"
        else:
            user.role = "admin"
            user.is_active = True
            action = "更新"
        user.set_password(password)
        db.commit()
        print(f"[create_admin] {action}管理员账号: {username}（密码已设置）")


if __name__ == "__main__":
    main()
