"""应用入口：FastAPI 装配、路由注册、前端静态托管。

启动：
    uvicorn bootstrap.main:app --host 0.0.0.0 --port 8000
或：
    python -m bootstrap.main
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.error_handlers import register_exception_handlers
from api.routes import admin, auth, chat, conversations, knowledge
from bootstrap.settings import PROJECT_ROOT, settings
from core.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="垂直行业智能客服 Agent：意图识别 + RAG 检索 + 多轮记忆 + 问题分流/归档",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    # 接口路由
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(knowledge.router)
    app.include_router(admin.router)

    # 健康检查
    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "app": settings.app_name})

    # 前端静态托管
    frontend_dir = Path(settings.frontend_dir)
    static_dir = frontend_dir / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(frontend_dir / "index.html")

    @app.get("/admin", include_in_schema=False)
    async def admin_page():
        return FileResponse(frontend_dir / "admin.html")

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()  # 开发快速开始：自动建表；生产建议用 Alembic
        logger.info("%s 启动完成，前端目录: %s", settings.app_name, frontend_dir)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bootstrap.main:app", host="0.0.0.0", port=8000, reload=True)
