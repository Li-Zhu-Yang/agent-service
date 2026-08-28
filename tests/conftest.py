"""测试全局夹具。

测试环境约定：
- 数据库：文件 SQLite（data/test.db），每个测试重建表
- Embedding：hash 向量（零下载零 key）
- 缓存：内存（REDIS_ENABLED=false）
- 向量库：data/test_chroma
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'data' / 'test.db').as_posix()}"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["REDIS_ENABLED"] = "false"
os.environ["CHROMA_DIR"] = str(ROOT / "data" / "test_chroma")
os.environ["JWT_SECRET"] = "test-secret"
os.environ["LLM_API_KEY"] = ""
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from bootstrap.main import app  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
from core.redis_client import cache  # noqa: E402
from core.vector_store import vector_store  # noqa: E402
from models.base import Base  # noqa: E402
from models.user import User  # noqa: E402
from rag.retrieval.retriever import invalidate_bm25_cache  # noqa: E402


@pytest.fixture(autouse=True)
async def _clean_everything():
    """每个测试：重建表 + 清空缓存与向量库。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    invalidate_bm25_cache()
    await vector_store.reset()
    await cache.close()  # 清空内存缓存
    yield
    await cache.close()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


@pytest.fixture
async def admin_token(client, db_session) -> str:
    """预置管理员并返回登录 token。"""
    user = db_session.query(User).filter(User.username == "admin").first()
    if user is None:
        user = User(username="admin", role="admin", display_name="管理员", is_active=True)
        user.set_password("admin123")
        db_session.add(user)
        db_session.commit()
    res = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


async def seed_kb(text: str = ""):
    """注入知识库（供检索/Agent 测试）。"""
    from rag.ingestion.pipeline import ingest_text

    demo = text or """# 退换货
## 七天无理由退货
问：支持七天无理由退货吗？
答：支持。自签收之日起 7 天内，商品未使用、不影响二次销售，可申请无理由退货。
## 退款流程
问：退款多久到账？
答：审核通过后，支付宝/微信 1-3 个工作日到账，银行卡 3-7 个工作日。
"""
    stats = await ingest_text(doc_id="test-doc-1", title="退换货与退款流程", text=demo)
    return stats
