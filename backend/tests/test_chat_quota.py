"""每日消息配额与消息长度上限单测（api-abuse-protection Phase 5.1 / 6.1）。

- 消息长度：超长 → 422（业务层未触达），用 pydantic 校验直测
- 配额：第 51 条拒绝且不触达 Agent；流式降级帧结构与既有降级帧完全一致；Redis 不可用放行
"""

import json

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import ChatMessageRequest
from app.utils.security import create_access_token

settings = get_settings()


# ── 消息长度（Phase 5.1）─────────────────────────────────────────────────


class TestMessageMaxLength:

    def test_message_within_limit_accepted(self):
        req = ChatMessageRequest(message="x" * 100)
        assert req.message == "x" * 100

    def test_message_over_limit_rejected(self):
        """5001 字消息 → 422（pydantic 校验在请求入口拦截，业务层未被触达）"""
        with pytest.raises(ValidationError):
            ChatMessageRequest(message="x" * (settings.CHAT_MESSAGE_MAX_LENGTH + 1))

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessageRequest(message="")


# ── 每日消息配额（Phase 6.1）─────────────────────────────────────────────


def _quota_key(user_id) -> str:
    from app.api.v1.chat import _quota_key

    return _quota_key(user_id)


@pytest_asyncio.fixture
async def quota_user_headers(test_db, client):
    """带 access token 的用户头"""
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(test_db)
    user = await user_repo.create(username="quota_user", password="Password123!")
    await test_db.commit()
    token = create_access_token(data={"sub": str(user.id)}, expires_delta=None)
    return {"Authorization": f"Bearer {token}"}, user.id


@pytest.mark.asyncio
class TestDailyQuota:

    async def test_non_stream_429_when_quota_exhausted(
        self, client, test_db, fake_redis, quota_user_headers
    ):
        headers, user_id = quota_user_headers

        # 新建会话（归属本人）
        from app.models import ChatSession

        session = ChatSession(user_id=user_id, title="新对话")
        test_db.add(session)
        await test_db.commit()

        # 预置配额已满
        await fake_redis.set(_quota_key(user_id), settings.CHAT_DAILY_MESSAGE_LIMIT)

        resp = await client.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "你好"},
            headers=headers,
        )
        assert resp.status_code == 429
        assert "今日对话次数已用完" in resp.json()["detail"]

    async def test_stream_quota_exceeded_uses_degradation_frame(
        self, client, test_db, fake_redis, quota_user_headers
    ):
        """流式超限：复用 llm-service-resilience 降级帧（token + final_response），无新增帧类型"""
        headers, user_id = quota_user_headers

        from app.models import ChatSession

        session = ChatSession(user_id=user_id, title="新对话")
        test_db.add(session)
        await test_db.commit()

        await fake_redis.set(_quota_key(user_id), settings.CHAT_DAILY_MESSAGE_LIMIT)

        resp = await client.post(
            f"/api/v1/chat/sessions/{session.id}/messages/stream",
            json={"message": "你好"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = []
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))

        types = [e["type"] for e in events]
        assert types == ["token", "final_response"]  # 与既有降级帧结构完全一致
        assert "今日对话次数已用完" in events[0]["data"]

    async def test_allows_when_redis_down(
        self, client, test_db, broken_redis, quota_user_headers
    ):
        """Redis 不可用 → 放行（防护失效优于业务不可用）"""
        headers, user_id = quota_user_headers

        from app.models import ChatSession

        session = ChatSession(user_id=user_id, title="新对话")
        test_db.add(session)
        await test_db.commit()

        # 配额检查放行后请求会进入 Agent（本地无 LLM 依赖时失败），
        # 但失败点必须是 Agent/LLM 层而非配额 429
        resp = await client.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "你好"},
            headers=headers,
        )
        assert resp.status_code != 429
