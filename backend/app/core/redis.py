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


async def incr_with_ttl(key: str, ttl: int) -> int | None:
    """固定窗口计数：SET key 0 EX ttl NX 原子建键（带 TTL），再 INCR。

    替代"INCR 后仅首次 EXPIRE"两步写：若 INCR 成功而 EXPIRE 失败，
    会产生无 TTL 的永久计数键（如 reparse:{id} 永久限 3 次不重置）。
    SET NX 幂等：键已存在时返回 None，直接 INCR 继续，TTL 不被重置（固定窗口语义）。
    Redis 不可用时返回 None（调用方按降级放行处理）。
    """
    client = get_redis()
    try:
        await client.set(key, 0, ex=ttl, nx=True)
        return await client.incr(key)
    except Exception as e:
        logger.warning("redis_unavailable_allow", error=str(e))
        return None
