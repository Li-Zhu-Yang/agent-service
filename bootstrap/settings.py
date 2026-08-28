"""全局配置（Pydantic Settings）。

从项目根目录 .env 加载，未填写时使用内置默认值（SQLite + 本地 embedding）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 bootstrap/ 下，上一级即根）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "ragent-py 智能客服"
    app_version: str = "0.1.0"
    debug: bool = False

    # ---- 大模型 ----
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.3

    # ---- Embedding ----
    embedding_provider: str = "chroma_local"  # chroma_local | dashscope | openai_compatible
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    # chroma_local 模型下载目录（默认放在项目 data/models 下）
    embedding_model_dir: str = str(PROJECT_ROOT / "data" / "models")

    # ---- 数据库 / Redis ----
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'ragent.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True  # 设为 false 可强制走内存降级

    # ---- 向量库 ----
    chroma_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_collection: str = "customer_service_kb"

    # ---- 认证 ----
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # ---- Agent 参数 ----
    context_window: int = 10
    qa_cache_ttl: int = 600
    retrieval_timeout: int = 5
    retrieval_top_k: int = 6
    retrieval_rerank_top_k: int = 4
    rate_limit_per_minute: int = 60
    # 转人工触发阈值：意图置信度低于该值
    intent_confidence_threshold: float = 0.45
    # 连续未解决轮数阈值
    unresolved_rounds_threshold: int = 2

    # ---- 演示账号 ----
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # ---- 前端静态目录 ----
    frontend_dir: str = str(PROJECT_ROOT / "frontend")

    # Chroma 本地默认 embedding 的模型名（镜像不可达时可手动放置模型）
    local_embedding_model: str = "all-MiniLM-L6-v2"

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
