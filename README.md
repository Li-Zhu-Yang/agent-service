# ragent-py 智能客服 Agent

垂直行业客服智能问答 Agent：**大模型轻量化微调思路 + RAG 融合架构**，为企业构建专属智能客服。替代传统规则化机器人，实现咨询智能识别、场景化应答、问题自动分流、疑难问题归档，适配高并发接待场景。

技术栈：**FastAPI + LangGraph + Chroma + Redis + DeepSeek**（大模型层 OpenAI 兼容，可切换任意服务商）。

---

## 核心能力

| 模块 | 说明 |
| --- | --- |
| 🧠 意图分层识别 | 关键词规则快速命中（低延迟）→ LLM 零样本 few-shot 兜底；低置信自动澄清/转人工 |
| 📚 行业专属知识库 | 支持 PDF / Word / Markdown / TXT 入库；垂直行业分块规则（保留问-答配对、短文本不硬切） |
| 🔎 混合检索 | 向量（Chroma）+ BM25 多路召回 → RRF 融合 → 重排；检索超时兜底 |
| 💬 多轮状态记忆 | 会话短期记忆（Redis/内存）+ 长期用户画像（DB），无需用户重复提问 |
| 🎫 问题分流与归档 | 简单问题 Agent 应答；低置信/投诉/连续未解决自动转人工并创建工单，同步对话记录 |
| 📊 每日运营报表 | 未解决量、高频问题、意图分布、响应时长、缓存命中率聚合（脚本 + 后台可视化） |
| ⚡ 高并发适配 | 高频问答缓存、热门知识预加载、IP 限流、SSE 流式首字优化、超时控制 |
| 🛠️ MCP 工具服务 | 标准 MCP stdio 服务，暴露订单/退款/知识检索/转人工工具供外部 Agent 调用 |
| 🔐 运营后台 | JWT 认证的管理端：概览 / 工单 / 报表 / 知识库管理 / 会话记录 |

---

## 快速开始（本地）

> 环境要求：Python 3.11+（推荐 3.12；3.14 个别依赖可能无预编译轮子）
> 中国网络建议 pip 使用清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple`

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate      # macOS / Linux
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 配置环境变量（复制模板并填写 LLM_API_KEY）
copy .env.example .env           # Windows
# cp .env.example .env           # macOS / Linux

# 3. 初始化数据库 + 创建管理员 + 注入演示知识库
python -m scripts.init_db
python -m scripts.create_admin
python -m scripts.seed_demo_kb

# 4. 启动
uvicorn bootstrap.main:app --host 0.0.0.0 --port 8000
# 或：python -m bootstrap.main
```

浏览器打开：

- 客服聊天页：http://127.0.0.1:8000/
- 运营后台：http://127.0.0.1:8000/admin（管理员 `admin / admin123`，可在 .env 修改）
- API 文档：http://127.0.0.1:8000/docs

> 💡 **无 API Key 也能跑**：默认 Embedding 用本地 ONNX（免 key），意图识别走规则；配置 `LLM_API_KEY` 后自动启用 LLM 意图识别与知识库回答生成。见下方「Embedding 说明」。

---

## 配置说明（.env）

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 空 | DeepSeek / 任意 OpenAI 兼容服务 key |
| `LLM_BASE_URL` | `https://api.deepseek.com` | 可切换 `https://api.openai.com/v1`、Ollama、通义等 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `EMBEDDING_PROVIDER` | `chroma_local` | `chroma_local`（本地ONNX）/ `hash`（零依赖兜底）/ `dashscope` / `openai_compatible` |
| `DATABASE_URL` | SQLite `./data/ragent.db` | PostgreSQL：`postgresql+psycopg://user:pass@host:port/db` |
| `REDIS_URL` | `redis://localhost:6379/0` | 无 Redis 自动降级进程内缓存 |
| `JWT_SECRET` | 默认值 | **生产必须修改** |
| `CONTEXT_WINDOW` | 10 | 会话上下文保留轮数 |
| `QA_CACHE_TTL` | 600 | 高频问答缓存秒数 |
| `RATE_LIMIT_PER_MINUTE` | 60 | 每 IP 每分钟请求上限 |

### Embedding 说明

DeepSeek 不提供向量 API，项目默认用 **Chroma 内置 ONNX 本地模型**（免 key、轻量，契合「知识库轻量化」）；若模型首次下载受网络影响，可设 `EMBEDDING_PROVIDER=hash` 走零依赖哈希向量（配合 BM25 可开箱即用）。需要更高质量中文向量时，接入 DashScope 或任意 OpenAI 兼容向量服务：

```env
EMBEDDING_PROVIDER=dashscope
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-v3
```

---

## 架构

```
bootstrap/   启动与配置（FastAPI 入口 / Pydantic Settings）
core/        基础设施（DB / Redis缓存 / Chroma向量库 / LLM / Embedding / 限流）
api/         接口层（chat SSE / conversations / knowledge / admin / auth）
agent/       Agent 引擎
  ├─ graph/      LangGraph 工作流：intent → retrieval → tool_call → response
  ├─ memory/     短期记忆（Redis）+ 长期画像（DB）
  ├─ tools/      订单 / 退款 / 转人工 / 天气
  └─ intent.py   意图分层识别（规则 + few-shot）
rag/         RAG 引擎（解析 → 行业分块 → 入库；向量+BM25 → RRF → 重排）
system/      认证 / 用户 / 审计 / 报表
mcp_server/  MCP stdio 服务
models/      SQLAlchemy ORM
migrations/  Alembic 迁移
frontend/    原生 JS 聊天页 + 运营后台
scripts/     运维脚本（init_db / create_admin / seed_demo_kb / 报表 / 样本导出）
tests/       pytest（意图 / 检索 / Agent全链路 / API）
docs/        文档
```

### Agent 工作流

```
用户输入
  │
  ▼
[intent] 规则命中？→ LLM few-shot → 置信度
  │
  ├─ 问候/转人工/投诉 ──────────────► [tool_call]
  ▼
[retrieval] 向量+BM25 混合检索（跳过场景除外）
  ▼
[tool_call] 转人工判定 / 订单·退款工具调用
  ▼
[response] 高频缓存 → LLM 流式生成（融合知识+工具结果）
  ▼
SSE 流式输出 + 会话落库 + 记忆更新
```

### 问题分流规则

自动转人工条件（任一命中）：

1. 用户主动要求「转人工」
2. 意图为投诉（敏感问题）
3. 意图置信度低于阈值 `INTENT_CONFIDENCE_THRESHOLD`
4. 连续 `UNRESOLVED_ROUNDS_THRESHOLD` 轮未能解决

转人工时自动创建工单，同步完整对话记录、问题摘要、意图与置信度。

---

## 测试

```bash
pytest -q
```

测试使用 SQLite + hash 向量 + 内存缓存，不依赖外网与 API Key，离线可跑通。

## MCP 服务

```bash
python -m mcp_server
```

在 Claude Desktop / Cursor 等支持 MCP 的客户端中，用 `stdio` 方式接入并指向该命令即可调用订单查询、退款申请、知识检索、转人工等工具。

## Docker 部署

```bash
# 仅起依赖（PostgreSQL + Redis）
docker compose up -d

# 构建应用镜像
docker build -t ragent-py .
docker run --rm -p 8000:8000 --env-file .env ragent-py
```

生产建议：`DATABASE_URL` 切 PostgreSQL，`REDIS_URL` 指向 Redis，`uvicorn --workers N` 多进程部署，前端静态页可由 Nginx 托管。

---

## 目录速查

```
智能客服/
├── bootstrap/            # FastAPI 应用入口
├── core/                 # 基础设施
├── api/routes/           # 接口
├── agent/                # Agent 引擎
├── rag/                  # RAG 引擎
├── system/               # 认证/报表/审计
├── mcp_server/           # MCP 服务
├── models/  schemas/     # ORM 与 Pydantic
├── migrations/           # Alembic
├── frontend/             # 网页聊天 + 后台
├── scripts/              # 运维脚本
├── tests/  docs/         # 测试与文档
└── docker-compose.yml / Dockerfile / requirements.txt
```

更多细节见 [docs/架构说明.md](docs/架构说明.md)。
