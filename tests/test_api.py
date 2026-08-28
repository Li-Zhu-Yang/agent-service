"""API 集成测试：健康检查 / 登录 / SSE 对话 / 知识库 / 后台。"""
from __future__ import annotations

import json


async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


async def test_login(client, admin_token):
    assert admin_token


async def test_login_wrong_password(client, db_session):
    from models.user import User

    user = User(username="u1", role="user", display_name="", is_active=True)
    user.set_password("pass123")
    db_session.add(user)
    db_session.commit()

    res = await client.post("/api/auth/login", json={"username": "u1", "password": "wrong"})
    assert res.status_code == 401


async def test_chat_stream_sse(client):
    async with client.stream(
        "POST", "/api/chat/stream", json={"message": "你好"}
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        buf = ""
        session_id = None
        done_payload = None
        async for chunk in res.aiter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                data = "".join(
                    line[6:] for line in block.splitlines() if line.startswith("data: ")
                )
                if not data:
                    continue
                evt = json.loads(data)
                if evt.get("session_id") and not done_payload:
                    session_id = evt["session_id"]
                if evt.get("intent") is not None:
                    done_payload = evt
        assert session_id
        assert done_payload is not None
        assert done_payload["intent"] == "greeting"
        assert "您好" in done_payload["answer"]


async def test_chat_requires_rate_limit_header(client):
    """正常请求即可，确认不报错即可（限流默认 60/min）。"""
    res = await client.post(
        "/api/chat/stream", json={"message": "在吗"}, headers={"Accept": "text/event-stream"}
    )
    assert res.status_code == 200


async def test_knowledge_admin_protected(client):
    res = await client.get("/api/knowledge/documents")
    assert res.status_code == 401


async def test_knowledge_search(client, admin_token):
    from tests.conftest import seed_kb

    await seed_kb()
    res = await client.post(
        "/api/knowledge/search",
        json={"query": "退款多久到账", "top_k": 3},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data
    assert any("退款" in item["chunk"] for item in data)


async def test_knowledge_text_ingest(client, admin_token):
    res = await client.post(
        "/api/knowledge/text",
        json={"title": "测试文档", "text": "# 测试\n\n问：你好吗？\n答：我很好。"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["chunk_count"] >= 1


async def test_admin_overview(client, admin_token):
    res = await client.get(
        "/api/admin/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "total_conversations" in data


async def test_admin_daily_report(client, admin_token):
    res = await client.get(
        "/api/admin/reports/daily", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    assert "total_questions" in res.json()["data"]
