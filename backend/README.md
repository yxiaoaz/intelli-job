# Intelli-Job Backend

FastAPI backend for Intelli-Job AI-powered job matching platform.

## 技术栈

- **Framework**: FastAPI
- **Database**: PostgreSQL (async with SQLAlchemy)
- **Cache**: Redis
- **Vector DB**: Zilliz Cloud (Milvus)
- **AI/ML**: LangChain + LangGraph (DeepAgents), DeepSeek API
- **Authentication**: JWT (PyJWT + bcrypt)

## 项目结构

```
backend/
├── app/
│   ├── api/v1/          # API路由 (auth, jobs, chat)
│   ├── core/agents/     # LangChain Agents
│   ├── services/        # 服务层 (LLM, VectorDB, JobMatching)
│   ├── repositories/    # 数据访问层
│   ├── models/          # SQLAlchemy模型
│   ├── schemas/         # Pydantic schemas
│   ├── utils/           # 工具函数
│   └── middleware/      # 中间件
├── tests/               # 测试代码
└── requirements.txt     # Python依赖
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填写必要的配置
```

必要的环境变量：
- `DATABASE_URL`: PostgreSQL连接字符串
- `REDIS_URL`: Redis连接字符串
- `DEEPSEEK_API_KEY`: DeepSeek API密钥
- `ZILLIZ_URI` & `ZILLIZ_TOKEN`: Zilliz Cloud配置
- `JWT_SECRET_KEY`: JWT签名密钥

### 3. 数据库迁移

```bash
# 初始化Alembic (首次)
alembic init migrations

# 生成迁移脚本
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

### 4. 启动服务

#### 方式一：快速启动（推荐）⭐

```bash
# 直接运行启动脚本
python run_local.py
```

这是最简单的启动方式，会自动：
- 加载 `.env` 配置
- 启用热重载（代码修改自动重启）
- 监听 `0.0.0.0:8000`

#### 方式二：使用 uvicorn 命令

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API端点

### 认证
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/refresh` - 刷新Token
- `GET /api/v1/auth/me` - 获取当前用户信息

### 职位
- `POST /api/v1/jobs/match` - 匹配职位
- `GET /api/v1/jobs/{job_id}` - 获取职位详情

### AI对话
- `POST /api/v1/chat/sessions` - 创建对话会话
- `POST /api/v1/chat/sessions/{id}/messages` - 发送消息
- `GET /api/v1/chat/sessions` - 获取会话列表

## 开发指南

### 添加新的API端点

1. 在 `app/api/v1/` 创建新的路由文件
2. 定义Pydantic schemas在 `app/schemas/`
3. 实现业务逻辑在 `app/services/`
4. 添加数据访问方法在 `app/repositories/`
5. 在 `app/main.py` 注册路由

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## Docker部署

```bash
# 构建镜像
docker build -t intelli-job-backend .

# 运行容器
docker run -p 8000:8000 --env-file .env intelli-job-backend
```

## 监控与日志

应用使用structlog进行结构化日志记录。日志输出包含：
- 请求路径
- 用户ID（如果认证）
- 错误详情
- 性能指标

查看日志示例：
```
2026-05-30 10:30:45 [info] job_matching_started search_mode=hybrid top_k=100
2026-05-30 10:30:47 [info] job_matching_completed result_count=50
```

## 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## License

MIT License
