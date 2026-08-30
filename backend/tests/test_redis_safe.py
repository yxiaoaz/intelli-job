"""Redis 封装与降级单测（api-abuse-protection Phase 1）。

fakeredis 打桩，不得直连 .env 的 Redis Cloud 实例。
"""

import pytest

from app.core.redis import get_redis, safe_redis


@pytest.mark.asyncio
class TestSafeRedis:

    async def test_normal_operation(self, fake_redis):
        """Redis 正常 → 计数/读写正确"""
        count = await safe_redis(lambda: get_redis().incr("unit_test:key"))
        assert count == 1
        assert await fake_redis.get("unit_test:key") == "1"

    async def test_returns_none_on_connection_error(self, broken_redis):
        """Redis 抛连接异常 → safe_redis 返回 None 且不抛出（业务放行）"""
        result = await safe_redis(lambda: get_redis().incr("unit_test:key"))
        assert result is None

    async def test_get_redis_is_singleton(self, fake_redis):
        assert get_redis() is fake_redis
        assert get_redis() is get_redis()


@pytest.mark.asyncio
class TestFakeRedisTtl:

    async def test_ttl_only_set_on_first_incr_semantics(self, fake_redis):
        """验证 fakeredis 能支撑"仅首次 INCR 设 TTL"的固定窗口断言"""
        key = "unit_test:fixed_window"
        assert await get_redis().incr(key) == 1
        await get_redis().expire(key, 900)
        assert 0 < await fake_redis.ttl(key) <= 900

        # 二次 INCR 不重置 TTL：先缩短到 500，再 INCR，TTL 仍 ≤500
        await fake_redis.expire(key, 500)
        await get_redis().incr(key)
        assert await fake_redis.ttl(key) <= 500
