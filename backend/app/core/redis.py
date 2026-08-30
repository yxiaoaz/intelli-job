"""Redis 客户端封装（懒加载单例 + 降级辅助）。

登录锁定、每日消息配额、reparse 限次等计数防护共用此入口。
与爬虫 job_crawler/pipelines.py 共用同一 Redis Cloud 实例：
新增 key 必须带业务前缀（chat_quota: / login_fail: / login_fail_lock: / reparse:），
与爬虫的 parsed_url 哈希键（无 TTL hash）互不冲突。
"""

from collections.abc import Awaitable, Callable

import redis.asyncio as redis

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger()

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """懒加载单例客户端（decode_responses=True，计数字符串直读）"""
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


async def safe_redis(op: Callable[[], Awaitable]):
    """执行 Redis 操作，异常时返回 None 并记 warning（调用方按 None 处理为放行）。

    降级哲学：防护失效优于业务不可用（redis_unavailable_allow）。
    用法: count = await safe_redis(lambda: get_redis().incr(key))
    """
    try:
        return await op()
    except Exception as e:
        logger.warning("redis_unavailable_allow", error=str(e))
        return None
