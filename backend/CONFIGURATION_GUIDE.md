# Backend 配置指南

## 📋 环境变量配置说明

本文档详细说明 `backend/.env` 文件中所有必需和可选的配置项。

---

## 🔑 必需配置项

### 1. LLM - Completion (DeepSeek)

用于AI对话和文本生成的模型配置。

```env
LLM_COMPLETION_API_KEY=sk-xxxxxxxxx
LLM_COMPLETION_API_URL=https://api.deepseek.com
LLM_COMPLETION_API_MODEL_NAME=deepseek-chat
```

**获取方式**:
1. 访问 [DeepSeek Platform](https://platform.deepseek.com/)
2. 注册账号并创建 API Key
3. 复制 API Key 到配置文件

---

### 2. LLM - Embedding (Alibaba Qwen)

用于生成文本嵌入向量（向量搜索）。

```env
LLM_EMBEDDING_API_KEY=sk-xxxxxxxxx
LLM_EMBEDDING_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_EMBEDDING_API_MODEL_NAME=text-embedding-v4
```

**获取方式**:
1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 开通通义千问服务
3. 创建 API Key
4. 复制 API Key 到配置文件

---

### 3. Zilliz Cloud (Vector Database)

向量数据库，用于职位语义搜索。

```env
ZILLIZ_URI=https://xxx.serverless.xxx.cloud.zilliz.com
ZILLIZ_TOKEN=xxxxxxxxx
ZILLIZ_JOB_ITEM_COLLECTION_NAME=intelli_job_job_items
```

**获取方式**:
1. 访问 [Zilliz Cloud](https://cloud.zilliz.com/)
2. 创建免费集群
3. 获取 Cluster Endpoint (URI) 和 API Token
4. 在集群中创建 Collection（或使用默认名称）

---

### 4. PostgreSQL RDS (Database)

关系型数据库，存储用户、职位、收藏等数据。

```env
RDS_DRIVERNAME=postgresql+pg8000
RDS_USERNAME=intelli_job_admin
RDS_PASSWORD=your_password
RDS_HOST=pgm-xxx.rds.aliyuncs.com
RDS_PORT=1827
RDS_DB_NAME=intelli_job
```

**获取方式**:
1. 阿里云 RDS for PostgreSQL
2. 创建数据库实例
3. 创建数据库和用户
4. 获取连接信息

**注意**: 
- 驱动名可以使用 `postgresql+asyncpg` (推荐) 或 `postgresql+pg8000`
- 确保数据库允许远程连接（配置白名单）

---

### 5. Redis (Cache)

缓存系统，用于加速查询和存储会话。

```env
REDIS_HOST=redis-xxx.redis-cloud.com
REDIS_PASSWORD=your_password
REDIS_PORT=6379
REDIS_DB=0
```

**获取方式**:
- 选项1: 阿里云 Redis
- 选项2: Redis Cloud (免费层)
- 选项3: 本地 Redis (`localhost`)

**本地开发配置**:
```env
REDIS_HOST=localhost
REDIS_PASSWORD=
REDIS_PORT=6379
REDIS_DB=0
```

---

### 6. JWT (Authentication)

用户认证令牌配置。

```env
JWT_SECRET_KEY=change-this-secret-key-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**安全建议**:
- 生产环境必须使用强随机密钥
- 生成方法: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## 📦 可选配置项

### Aliyun OSS (Object Storage)

用于存储用户上传的简历文件。

```env
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=intellijob-resumes
```

**说明**:
- 如果不配置，简历上传功能将不可用
- 可以后续添加，不影响其他功能

---

### Rate Limiting

API 速率限制配置。

```env
RATE_LIMIT_PER_MINUTE=30
```

**说明**:
- 每个用户每分钟最多 30 次请求
- 可根据需要调整

---

### Application Settings

应用基本信息。

```env
APP_NAME=Intelli-Job API
APP_VERSION=1.0.0
DEBUG=False
```

**说明**:
- `DEBUG=True` 时启用详细日志和错误信息
- 生产环境务必设置为 `False`

---

## 🔧 配置示例

### 完整配置示例 (.env)

```env
# Application
APP_NAME=Intelli-Job API
APP_VERSION=1.0.0
DEBUG=True

# Database
RDS_DRIVERNAME=postgresql+asyncpg
RDS_USERNAME=postgres
RDS_PASSWORD=mypassword
RDS_HOST=localhost
RDS_PORT=5432
RDS_DB_NAME=intellijob

# Redis
REDIS_HOST=localhost
REDIS_PASSWORD=
REDIS_PORT=6379
REDIS_DB=0

# JWT
JWT_SECRET_KEY=super-secret-key-for-development-only
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM - Completion
LLM_COMPLETION_API_KEY=sk-your-deepseek-key
LLM_COMPLETION_API_URL=https://api.deepseek.com
LLM_COMPLETION_API_MODEL_NAME=deepseek-chat

# LLM - Embedding
LLM_EMBEDDING_API_KEY=sk-your-qwen-key
LLM_EMBEDDING_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_EMBEDDING_API_MODEL_NAME=text-embedding-v4

# Zilliz Cloud
ZILLIZ_URI=https://your-cluster.zilliz.com
ZILLIZ_TOKEN=your-token
ZILLIZ_JOB_ITEM_COLLECTION_NAME=job_items

# Aliyun OSS (Optional)
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=intellijob-resumes

# Rate Limiting
RATE_LIMIT_PER_MINUTE=30
```

---

## ❓ 常见问题

### Q1: 如何生成安全的 JWT_SECRET_KEY？

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Q2: 本地开发没有 Redis 怎么办？

可以使用 Docker 快速启动 Redis：

```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

然后配置：
```env
REDIS_HOST=localhost
REDIS_PASSWORD=
```

### Q3: 本地开发没有 PostgreSQL 怎么办？

使用 Docker：

```bash
docker run -d \
  --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=intellijob \
  -p 5432:5432 \
  postgres:15
```

然后配置：
```env
RDS_DRIVERNAME=postgresql+asyncpg
RDS_USERNAME=postgres
RDS_PASSWORD=password
RDS_HOST=localhost
RDS_PORT=5432
RDS_DB_NAME=intellijob
```

### Q4: 如何测试配置是否正确？

启动服务后访问健康检查端点：

```bash
curl http://localhost:8000/health
```

如果返回 `{"status": "healthy"}`，说明配置正确。

### Q5: 出现 "validation errors for Settings" 怎么办？

检查以下几点：
1. `.env` 文件是否存在于 `backend/` 目录
2. 变量名是否与 `config.py` 中定义的一致
3. 是否有多余的空格（应该用 `KEY=value` 而不是 `KEY = value`）
4. 所有必需的字段是否都已填写

---

## 🔐 安全注意事项

1. **永远不要**将 `.env` 文件提交到 Git
2. **生产环境**必须使用强密码和密钥
3. **定期轮换** API Keys 和数据库密码
4. **限制**数据库和 Redis 的访问 IP
5. **启用** SSL/TLS 加密连接

---

## 📚 相关文档

- [Backend README](README.md)
- [启动方式指南](STARTUP_GUIDE.md)
- [实施总结](../../docs/IMPLEMENTATION_SUMMARY.md)

---

**最后更新**: 2026-05-30
