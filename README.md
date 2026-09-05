# NWU Resource Hub（拾页）

校内资料分享与 AI 检索平台 MVP。用户通过校内邮箱注册，上传 PDF、Office 文档或图片并填写使用经验；后台完成安全扫描、文本提取、OCR、向量化和用途分析，搜索 Agent 只能查询已发布的站内资源。

## 功能

- 校内邮箱白名单、验证码注册、JWT 登录和 Refresh Token 单次轮换
- PDF、DOCX、PPTX、XLSX、PNG、JPEG 上传与文件签名验证
- Celery 异步解析、PaddleOCR、BGE-M3 和 DeepSeek 结构化分析
- 标题/课程/标签关键词与 pgvector 语义混合搜索
- DeepSeek 受控工具调用 Agent，不允许直接访问数据库
- 我的分享、AI 结果确认、资源发布、授权下载和个人存储配额
- 学院/专业/课程/老师/年级/年份筛选，按时间或点赞数排序
- 点赞、点踩、评论、分享者主页、匿名分享和首次使用引导
- 资源求助中心、同求热度榜和相似标题提示
- 举报阈值自动下架、管理员审核、操作审计、请求 ID 和 Redis 限流
- 私有 MinIO Bucket 与 5 分钟下载地址

## 技术栈

- Vue 3、TypeScript、Vite、Element Plus
- FastAPI、SQLAlchemy 2、Alembic、Pydantic 2
- PostgreSQL + pgvector、Redis、Celery、MinIO、ClamAV
- DeepSeek API、BGE-M3、PaddleOCR

## 轻量开发模式

轻量模式使用 SQLite、本地文件存储、同步任务和确定性的本地 AI 降级实现，不要求 Docker、Redis、DeepSeek Key 或 GPU。

```powershell
Copy-Item .env.example .env
(Get-Content .env) `
  -replace 'postgresql\+psycopg://campus:campus@postgres:5432/campus', 'sqlite:///./data/campus.db' `
  -replace 'STORAGE_BACKEND=minio', 'STORAGE_BACKEND=local' `
  -replace 'ENABLE_BACKGROUND_TASKS=true', 'ENABLE_BACKGROUND_TASKS=false' | Set-Content .env

uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

另开终端启动前端：

```powershell
cd frontend
npm ci
npm run dev
```

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

开发环境未配置 SMTP 时，邮箱验证码会写入 API 日志。未配置 DeepSeek Key 或未安装 AI 依赖时，系统使用本地摘要与哈希向量，确保基本流程可演示。

默认允许上传最大 200 MB 的文件。超过 `AI_PARSE_MAX_MB`（默认 50 MB）时仍会保存并允许发布，但跳过 OCR、向量化和 DeepSeek 内容解析，以避免大文件长期占用任务队列。

## 完整 Docker 环境

1. 复制 `.env.example` 为 `.env`。
2. 修改 `SECRET_KEY`、`ALLOWED_EMAIL_DOMAINS` 和 `ADMIN_EMAILS`。
3. 如需真实 AI 分析，配置 `DEEPSEEK_API_KEY`。
4. 启动 Docker Desktop 后运行：

```powershell
docker compose up --build
```

- Web：http://localhost:5173
- API 文档：http://localhost:8000/docs
- Mailpit：http://localhost:8025
- MinIO Console：http://localhost:9001

完整环境在 API 启动前执行 Alembic 迁移，并分别运行 API、Celery Worker 和 Celery Beat。ClamAV 只在容器 Worker 中启用；病毒库首次初始化可能需要几分钟。

## AI 依赖

基础依赖不会下载大型模型。需要本地 BGE-M3 和 PaddleOCR 时运行：

```powershell
uv sync --extra dev --extra ai
```

首次推理会下载模型，请确保有足够磁盘空间。生产环境建议将模型缓存挂载为持久卷，并在部署前预热。

## 验证

```powershell
uv run pytest
uv run ruff check app tests migrations
uv run alembic check
cd frontend
npm run typecheck
npm run build
```

正式上线前还应配置 HTTPS、可信 SMTP、强随机 `SECRET_KEY`、真实校内邮箱域名、备份策略以及内容与版权管理制度。
