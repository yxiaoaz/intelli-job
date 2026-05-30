@echo off
REM Intelli-Job Backend Windows快速启动脚本

echo =========================================
echo   Intelli-Job Backend 快速启动 (Windows)
echo =========================================
echo.

REM 检查Python版本
echo [1/6] 检查Python版本...
python --version
if errorlevel 1 (
    echo ❌ Python未安装，请先安装Python 3.10+
    pause
    exit /b 1
)
echo.

REM 创建虚拟环境
if not exist "venv" (
    echo [2/6] 创建虚拟环境...
    python -m venv venv
    echo    ✅ 虚拟环境创建成功
) else (
    echo [2/6] 虚拟环境已存在
)
echo.

REM 激活虚拟环境
echo [3/6] 激活虚拟环境...
call venv\Scripts\activate.bat
echo    ✅ 虚拟环境已激活
echo.

REM 安装依赖
echo [4/6] 安装依赖...
pip install -r requirements.txt --quiet
echo    ✅ 依赖安装完成
echo.

REM 检查.env文件
if not exist ".env" (
    echo [5/6] ⚠️  未找到 .env 文件
    echo        从 .env.example 复制模板...
    copy .env.example .env
    echo.
    echo ❗ 请编辑 .env 文件并填写以下必要配置:
    echo    - DATABASE_URL
    echo    - DEEPSEEK_API_KEY
    echo    - ZILLIZ_URI ^& ZILLIZ_TOKEN
    echo    - JWT_SECRET_KEY
    echo.
    pause
) else (
    echo [5/6] ✅ .env 文件已存在
)
echo.

REM 启动服务
echo =========================================
echo   🚀 启动FastAPI服务
echo =========================================
echo.
echo    API文档: http://localhost:8000/docs
echo    健康检查: http://localhost:8000/health
echo.
echo    按 Ctrl+C 停止服务
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
