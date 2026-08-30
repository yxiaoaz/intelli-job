"""登录防护单测（api-abuse-protection Phase 4）。

- 登录失败锁定：固定窗口（仅首次 INCR 设 TTL）、成功清零、锁定 429、Redis 降级放行
- /refresh 回库校验：被禁用用户的 refresh token → 401
"""

import pytest

from app.api.v1.auth import (
    _clear_login_failures,
    _is_login_locked,
    _login_fail_key,
    _login_lock_key,
    _record_login_failure,
)
from app.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
class TestLoginLockout:

    async def test_not_locked_initially(self, fake_redis):
        assert await _is_login_locked("alice") is False

    async def test_lock_after_max_failures(self, fake_redis):
        for _ in range(settings.LOGIN_MAX_FAILURES):
            await _record_login_failure("alice")
        assert await _is_login_locked("alice") is True

    async def test_below_threshold_not_locked(self, fake_redis):
        for _ in range(settings.LOGIN_MAX_FAILURES - 1):
            await _record_login_failure("bob")
        assert await _is_login_locked("bob") is False

    async def test_fixed_window_ttl_not_reset(self, fake_redis):
        """固定窗口语义：多次失败不重置 TTL（防“4 次/14.5 分钟”节奏永久爆破）"""
        await _record_login_failure("carol")
        await fake_redis.expire(_login_fail_key("carol"), 500)
        await _record_login_failure("carol")
        ttl = await fake_redis.ttl(_login_fail_key("carol"))
        assert 0 < ttl <= 500  # 未被重置回 LOGIN_LOCKOUT_MINUTES*60

    async def test_clear_on_success(self, fake_redis):
        await _record_login_failure("dave")
        await _record_login_failure("dave")
        await _clear_login_failures("dave")
        assert await fake_redis.get(_login_fail_key("dave")) is None

    async def test_lock_key_has_ttl(self, fake_redis):
        for _ in range(settings.LOGIN_MAX_FAILURES):
            await _record_login_failure("erin")
        ttl = await fake_redis.ttl(_login_lock_key("erin"))
        assert 0 < ttl <= settings.LOGIN_LOCKOUT_MINUTES * 60

    async def test_degrades_open_when_redis_down(self, broken_redis):
        """Redis 不可用 → 放行（不抛出，锁定不生效）"""
        await _record_login_failure("frank")
        assert await _is_login_locked("frank") is False

    async def test_username_normalized_to_lowercase(self, fake_redis):
        await _record_login_failure("Alice")
        assert await fake_redis.get(_login_fail_key("alice")) == "1"


@pytest.mark.asyncio
class TestLoginEndpointLockout:

    async def test_correct_password_rejected_after_lockout(self, client, test_user_data, fake_redis):
        """连续 N 次失败后，正确密码也返回 429"""
        resp = await client.post("/api/v1/auth/register", json=test_user_data)
        assert resp.status_code == 201

        wrong = {
            "username": test_user_data["username"],
            "password": "WrongPassword123",
        }
        for _ in range(settings.LOGIN_MAX_FAILURES):
            await client.post("/api/v1/auth/login", json=wrong)

        # 已锁定：正确密码也被拒
        resp = await client.post("/api/v1/auth/login", json=test_user_data)
        assert resp.status_code == 429
        assert "尝试次数过多" in resp.json()["detail"]

    async def test_login_works_when_redis_down(self, client, test_user_data, broken_redis):
        """Redis 不可用 → 登录功能正常（放行）"""
        resp = await client.post("/api/v1/auth/register", json=test_user_data)
        assert resp.status_code == 201

        resp = await client.post("/api/v1/auth/login", json=test_user_data)
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
class TestRefreshDbCheck:

    async def test_refresh_success(self, client, test_user_data, fake_redis):
        await client.post("/api/v1/auth/register", json=test_user_data)
        login_resp = await client.post("/api/v1/auth/login", json=test_user_data)
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_rejected_for_disabled_user(
        self, client, test_user_data, test_db, fake_redis
    ):
        """被禁用用户的 refresh token 在有效期内也不得续命 → 401"""
        from app.repositories.user_repo import UserRepository

        await client.post("/api/v1/auth/register", json=test_user_data)
        login_resp = await client.post("/api/v1/auth/login", json=test_user_data)
        refresh_token = login_resp.json()["refresh_token"]

        user_repo = UserRepository(test_db)
        user = await user_repo.get_by_username(test_user_data["username"])
        user.is_active = False
        await test_db.commit()

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401
