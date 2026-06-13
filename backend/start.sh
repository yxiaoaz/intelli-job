#!/bin/bash
# Intelli-Job Backend 快速启动脚本

set -e

echo "========================================="
echo "  Intelli-Job Backend 快速启动"
echo "========================================="
echo ""

# 检查Python版本
echo "📋 检查Python版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python版本: $python_version"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo ""
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
    echo "   ✅ 虚拟环境创建成功"
else
    echo "   ℹ️  虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "🔑 激活虚拟环境..."
source venv/bin/activate
echo "   ✅ 虚拟环境已激活"

# 安装依赖
echo ""
echo "📦 安装依赖..."
pip install -r requirements.txt --quiet
echo "   ✅ 依赖安装完成"

# 检查.env文件
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  未找到 .env 文件"
    echo "   从 .env.example 复制模板..."
    cp .env.example .env
    echo ""
    echo "❗ 请编辑 .env 文件并填写以下必要配置:"
    echo "   - DATABASE_URL"
    echo "   - DEEPSEEK_API_KEY"
    echo "   - ZILLIZ_URI & ZILLIZ_TOKEN"
    echo "   - JWT_SECRET_KEY"
    echo ""
    read -p "按回车键继续..."
fi

# 检查数据库
echo ""
echo "🗄️  检查数据库连接..."
if command -v psql &> /dev/null; then
    if psql -lqt | cut -d \| -f 1 | grep -qw intellijob; then
        echo "   ✅ 数据库 intellijob 已存在"
    else
        echo "   ⚠️  数据库不存在，正在创建..."
        createdb intellijob
        echo "   ✅ 数据库创建成功"
    fi
else
    echo "   ℹ️  请确保PostgreSQL正在运行且数据库已创建"
fi

# 初始化Alembic (如果未初始化)
if [ ! -d "migrations" ]; then
    echo ""
    echo "🔄 初始化Alembic迁移..."
    alembic init migrations
    echo "   ✅ Alembic初始化完成"
    
    echo ""
    echo "📝 生成初始迁移脚本..."
    alembic revision --autogenerate -m "Initial migration"
    
    echo ""
    echo "⬆️  执行数据库迁移..."
    alembic upgrade head
    echo "   ✅ 数据库迁移完成"
else
    echo ""
    echo "🔄 检查待执行的迁移..."
    alembic upgrade head
    echo "   ✅ 数据库已是最新"
fi

# 启动服务
echo ""
echo "========================================="
echo "  🚀 启动FastAPI服务"
echo "========================================="
echo ""
echo "   API文档: http://localhost:8000/docs"
echo "   健康检查: http://localhost:8000/health"
echo ""
echo "   按 Ctrl+C 停止服务"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
