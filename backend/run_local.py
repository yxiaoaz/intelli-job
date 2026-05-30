#!/usr/bin/env python3
"""
快速启动本地开发服务器

使用方法:
    python run_local.py

功能:
    - 自动加载 .env 配置
    - 启动 FastAPI 开发服务器
    - 启用热重载 (auto-reload)
    - 监听所有网络接口 (0.0.0.0)
"""

import uvicorn
import sys
import os

# 确保可以导入 app 模块
sys.path.insert(0, os.path.dirname(__file__))

# 检查必要的依赖是否已安装
try:
    import fastapi
    import sqlalchemy
    import langchain
except ImportError as e:
    print(f"❌ 缺少必要的依赖: {e}")
    print()
    print("请先安装依赖:")
    print("  pip install -r requirements.txt")
    print()
    print("或者激活虚拟环境:")
    print("  Windows: venv\\Scripts\\activate")
    print("  Linux/Mac: source venv/bin/activate")
    print()
    sys.exit(1)

def main():
    """启动本地开发服务器"""
    
    print("=" * 60)
    print("  🚀 Intelli-Job Backend - 本地开发服务器")
    print("=" * 60)
    print()
    
    # 检查 .env 文件
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_file):
        print("⚠️  警告: 未找到 .env 文件")
        print("   请从 .env.example 复制并填写必要配置")
        print()
    
    print("📡 服务器信息:")
    print("   - 地址: http://localhost:8000")
    print("   - API文档: http://localhost:8000/docs")
    print("   - 健康检查: http://localhost:8000/health")
    print()
    print("⚙️  配置:")
    print("   - 热重载: 启用")
    print("   - 调试模式: 启用")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()
    
    # 启动 Uvicorn 服务器
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,      # 启用热重载
            log_level="info"  # 日志级别
        )
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
