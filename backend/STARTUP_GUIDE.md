# Backend 启动方式指南

## 🚀 三种启动方式

### 方式一：快速启动（最简单）⭐

```bash
cd backend
python run_local.py
```

**优点**:
- ✅ 一键启动，无需记忆复杂命令
- ✅ 自动检查依赖是否安装
- ✅ 友好的错误提示
- ✅ 显示服务器信息和访问地址
- ✅ 自动启用热重载

**适用场景**: 日常开发、快速测试

---

### 方式二：使用启动脚本

#### Windows
```bash
cd backend
.\start.bat
```

#### Linux/Mac
```bash
cd backend
./start.sh
```

**优点**:
- ✅ 自动创建和激活虚拟环境
- ✅ 自动安装依赖
- ✅ 自动检查 .env 配置
- ✅ 完整的初始化流程

**适用场景**: 首次 setup、新环境部署

---

### 方式三：直接使用 uvicorn

```bash
cd backend

# 开发模式（带热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式（多进程）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**优点**:
- ✅ 完全控制所有参数
- ✅ 可以自定义端口、worker数量等
- ✅ 适合高级用户

**适用场景**: 需要自定义配置、生产部署

---

## 📋 启动前准备

### 1. 确保已安装依赖

```bash
pip install -r requirements.txt
```

或者使用 `start.bat` / `start.sh` 自动安装。

### 2. 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件，填写必要配置
# - DATABASE_URL
# - DEEPSEEK_API_KEY
# - ZILLIZ_URI & ZILLIZ_TOKEN
# - JWT_SECRET_KEY
```

### 3. （可选）数据库迁移

如果使用 PostgreSQL，需要先执行数据库迁移：

```bash
alembic upgrade head
```

---

## 🔍 验证服务是否启动成功

启动后，访问以下地址验证：

1. **健康检查**: http://localhost:8000/health
   - 应该返回: `{"status": "healthy"}`

2. **API文档**: http://localhost:8000/docs
   - Swagger UI 界面

3. **ReDoc文档**: http://localhost:8000/redoc
   - 更美观的API文档

---

## ⚙️ 自定义配置

如果需要修改默认配置，可以编辑 `run_local.py`：

```python
# 修改端口
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=9000,        # 改为 9000
    reload=True,
    log_level="info"
)

# 关闭热重载（生产环境）
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,
    reload=False,     # 关闭热重载
    log_level="warning"  # 降低日志级别
)
```

---

## ❓ 常见问题

### Q1: 提示 "ModuleNotFoundError: No module named 'fastapi'"

**原因**: 依赖未安装或虚拟环境未激活

**解决**:
```bash
# 安装依赖
pip install -r requirements.txt

# 或激活虚拟环境
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Q2: 提示 "未找到 .env 文件"

**原因**: 缺少环境变量配置

**解决**:
```bash
cp .env.example .env
# 然后编辑 .env 填写必要配置
```

### Q3: 端口 8000 已被占用

**原因**: 其他程序正在使用 8000 端口

**解决**:
```bash
# 方法1: 修改 run_local.py 中的端口号
port=9000  # 改为其他端口

# 方法2: 杀掉占用端口的进程
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

### Q4: 数据库连接失败

**原因**: DATABASE_URL 配置错误或数据库未启动

**解决**:
1. 检查 `.env` 中的 `DATABASE_URL` 是否正确
2. 确保 PostgreSQL 服务正在运行
3. 测试连接: `psql <DATABASE_URL>`

---

## 🎯 推荐工作流程

### 日常开发

```bash
# 1. 进入 backend 目录
cd backend

# 2. 激活虚拟环境（如果还没激活）
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 启动服务
python run_local.py

# 4. 开始开发，代码修改会自动重载
```

### 首次设置

```bash
# 1. 进入 backend 目录
cd backend

# 2. 运行启动脚本（自动完成所有配置）
# Windows
.\start.bat

# Linux/Mac
./start.sh

# 3. 按照提示编辑 .env 文件

# 4. 重新启动
python run_local.py
```

---

## 📊 三种方式对比

| 特性 | run_local.py | start.bat/sh | uvicorn |
|------|--------------|--------------|---------|
| **易用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **自动化程度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **灵活性** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **适用场景** | 日常开发 | 首次setup | 高级配置 |
| **依赖检查** | ✅ | ✅ | ❌ |
| **虚拟环境** | ❌ | ✅ | ❌ |
| **热重载** | ✅ | ✅ | 可选 |

---

## 💡 小贴士

1. **开发时推荐使用 `run_local.py`**，简单快捷
2. **首次部署使用 `start.bat/sh`**，自动化程度高
3. **生产环境直接使用 `uvicorn`**，完全控制参数
4. **记得配置 `.env` 文件**，否则服务无法正常启动
5. **查看日志输出**，可以快速定位问题

---

**最后更新**: 2026-05-30
