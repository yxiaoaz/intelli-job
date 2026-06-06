"""
清空 Redis 爬虫缓存（已抓取的 URL 去重记录）
用法: python scripts/clear_redis_cache.py
"""

import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, backend_dir)

import redis
from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(backend_dir, ".env"))

redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT", "10771"))
redis_password = os.getenv("REDIS_PASSWORD")

print(f"连接 Redis: {redis_host}:{redis_port}")

redis_db = redis.Redis(
    host=redis_host,
    port=redis_port,
    decode_responses=True,
    username="default",
    password=redis_password,
)

# 验证连接
redis_db.ping()
print("Redis 连接成功")

# 读取并清空 parsed_url 缓存
all_urls = redis_db.hgetall("parsed_url")
print(f"当前已缓存 URL 数量: {len(all_urls)}")

if all_urls:
    redis_db.hdel("parsed_url", *all_urls)
    remaining = len(redis_db.hgetall("parsed_url"))
    print(f"清空后剩余 URL 数量: {remaining}")
    print("Redis 缓存已清空")
else:
    print("缓存为空，无需清空")
