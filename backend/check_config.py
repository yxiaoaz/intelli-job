#!/usr/bin/env python3
"""
配置验证工具

使用方法:
    python check_config.py

功能:
    - 检查 .env 文件是否存在
    - 验证所有必需的配置项
    - 测试数据库连接（可选）
    - 提供详细的错误提示和修复建议
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def check_env_file():
    """检查 .env 文件是否存在"""
    env_path = Path(__file__).parent / ".env"
    
    if not env_path.exists():
        print("❌ 未找到 .env 文件")
        print()
        print("请从 .env.example 复制并填写配置:")
        print("  cp .env.example .env")
        print()
        return False
    
    print("✅ .env 文件存在")
    return True

def check_required_fields():
    """检查必需的配置字段"""
    print("\n📋 检查必需配置项...")
    print("=" * 60)
    
    required_fields = {
        "LLM_COMPLETION_API_KEY": "DeepSeek API Key",
        "LLM_EMBEDDING_API_KEY": "Qwen Embedding API Key",
        "ZILLIZ_URI": "Zilliz Cloud URI",
        "ZILLIZ_TOKEN": "Zilliz Cloud Token",
        "RDS_USERNAME": "Database Username",
        "RDS_PASSWORD": "Database Password",
        "RDS_HOST": "Database Host",
        "RDS_DB_NAME": "Database Name",
        "JWT_SECRET_KEY": "JWT Secret Key",
    }
    
    missing_fields = []
    
    # 读取 .env 文件
    env_path = Path(__file__).parent / ".env"
    env_vars = {}
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # 检查每个必需字段
    for field, description in required_fields.items():
        value = env_vars.get(field, "")
        
        if not value:
            print(f"  ❌ {field:30s} - 缺失")
            missing_fields.append((field, description))
        else:
            # 隐藏敏感信息
            masked_value = value[:4] + "*" * (len(value) - 4) if len(value) > 4 else "***"
            print(f"  ✅ {field:30s} - {masked_value}")
    
    if missing_fields:
        print()
        print("⚠️  以下必需配置项缺失:")
        for field, desc in missing_fields:
            print(f"   - {field}: {desc}")
        print()
        print("请编辑 .env 文件并填写这些配置项")
        return False
    
    print()
    print("✅ 所有必需配置项已填写")
    return True

def check_optional_fields():
    """检查可选配置字段"""
    print("\n📦 检查可选配置项...")
    print("=" * 60)
    
    optional_fields = {
        "OSS_ACCESS_KEY_ID": "Aliyun OSS Access Key ID",
        "OSS_ACCESS_KEY_SECRET": "Aliyun OSS Access Key Secret",
    }
    
    env_path = Path(__file__).parent / ".env"
    env_vars = {}
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    for field, description in optional_fields.items():
        value = env_vars.get(field, "")
        
        if not value:
            print(f"  ⚪ {field:30s} - 未配置 (可选)")
        else:
            print(f"  ✅ {field:30s} - 已配置")
    
    print()
    print("ℹ️  可选配置项不影响核心功能")
    return True

def test_imports():
    """测试关键依赖是否可以导入"""
    print("\n🔧 检查 Python 依赖...")
    print("=" * 60)
    
    required_packages = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic_settings", "Pydantic Settings"),
        ("langchain", "LangChain"),
        ("pymilvus", "PyMilvus"),
    ]
    
    missing_packages = []
    
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {name:30s} - 已安装")
        except ImportError:
            print(f"  ❌ {name:30s} - 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print()
        print("⚠️  缺少以下依赖包:")
        print("   请运行: pip install -r requirements.txt")
        return False
    
    print()
    print("✅ 所有依赖包已安装")
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("  🔍 Intelli-Job Backend - 配置验证工具")
    print("=" * 60)
    print()
    
    # 执行检查
    checks = [
        ("环境变量文件", check_env_file),
        ("必需配置项", check_required_fields),
        ("可选配置项", check_optional_fields),
        ("Python依赖", test_imports),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 检查失败: {e}")
            results.append((name, False))
    
    # 汇总结果
    print()
    print("=" * 60)
    print("  📊 检查结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
        if not result:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 所有检查通过！可以启动服务了。")
        print()
        print("运行命令:")
        print("  python run_local.py")
        print()
    else:
        print("⚠️  存在配置问题，请先修复后再启动服务。")
        print()
        print("参考文档:")
        print("  - CONFIGURATION_GUIDE.md")
        print("  - STARTUP_GUIDE.md")
        print()
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
