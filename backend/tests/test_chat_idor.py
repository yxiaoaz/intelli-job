"""IDOR 越权修复单测（api-abuse-protection Phase 3）。

用户 A 不得向用户 B 的会话注入消息 / 读取 / 删除 / 改标题；
stream 端点的 404 必须是 HTTP 响应而非 SSE error 帧。
"""

import uuid

import pytest
import pytest_asyncio

from app.models import ChatSession
from app.utils.security import create_access_token


async def _make_session(db, user_id, title="B 的会话") -> ChatSession:
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    await db.flush()
    return session


async def _make_user_with_token(db, username) -> tuple[str, uuid.UUID]:
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(db)
    user = await user_repo.create(username=username, password="Password123!")
    await db.commit()
    token = create_access_token(data={"sub": str(user.id)}, expires_delta=None)
    return token, user.id


@pytest_asyncio.fixture
async def owner_and_session(test_db, client):
    """用户 B（会话所有者）及其会话"""
    token_b, user_b_id = await _make_user_with_token(test_db, "owner_user")
    session = await _make_session(test_db, user_b_id)
    yield {"token_b": token_b, "user_b_id": user_b_id, "session": session}
    await test_db.rollback()


@pytest_asyncio.fixture
async def attacker_headers(test_db, client):
    """用户 A（攻击者）的 Authorization 头"""
    token_a, user_a_id = await _make_user_with_token(test_db, "attacker_user")
    return {"Authorization": f"Bearer {token_a}"}


@pytest.mark.asyncio
class TestChatIdor:

    async def test_send_message_to_foreign_session_404(
        self, client, test_db, owner_and_session, attacker_headers
    ):
        session = owner_and_session["session"]

        resp = await client.post(
            f"/api/v1/chat/sessions/{session.id}/messages",
            json={"message": "注入的消息"},
            headers=attacker_headers,
        )
        assert resp.status_code == 404

        # B 的会话消息数不变
        from sqlalchemy import select
        from app.models import ChatMessage

        result = await test_db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
        )
        assert len(result.scalars().all()) == 0

    async def test_send_message_stream_to_foreign_session_404(
        self, client, test_db, owner_and_session, attacker_headers
    ):
        session = owner_and_session["session"]

        resp = await client.post(
            f"/api/v1/chat/sessions/{session.id}/messages/stream",
            json={"message": "注入的消息"},
            headers=attacker_headers,
        )
        assert resp.status_code == 404
        # 404 是 HTTP 响应而非 SSE error 帧
        assert not resp.headers.get("content-type", "").startswith("text/event-stream")
        assert "会话不存在" in resp.json()["detail"]

    async def test_read_patch_delete_foreign_session_404(
        self, client, test_db, owner_and_session, attacker_headers
    ):
        session = owner_and_session["session"]
        base = f"/api/v1/chat/sessions/{session.id}"

        assert (await client.get(base, headers=attacker_headers)).status_code == 404
        assert (
            await client.get(f"{base}/messages", headers=attacker_headers)
        ).status_code == 404
        assert (
            await client.patch(base, json={"title": "hacked"}, headers=attacker_headers)
        ).status_code == 404
        assert (await client.delete(base, headers=attacker_headers)).status_code == 404

    async def test_owner_access_still_works(
        self, client, test_db, owner_and_session
    ):
        """所有者本人访问正常（403 → 404 收敛未误伤合法路径）"""
        token_b = owner_and_session["token_b"]
        session = owner_and_session["session"]
        headers = {"Authorization": f"Bearer {token_b}"}

        resp = await client.get(f"/api/v1/chat/sessions/{session.id}", headers=headers)
        assert resp.status_code == 200

    async def test_nonexistent_session_404(self, client, attacker_headers):
        """不存在的会话同样 404（与越权响应不可区分，防存在性泄露）"""
        random_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/chat/sessions/{random_id}", headers=attacker_headers
        )
        assert resp.status_code == 404
