"""求职意向端点测试 — GET/PUT /api/v1/chat/sessions/{id}/intent

覆盖 agent-context-overhaul E2E 验收发现的缺口：
- 后端在 memory-system-redesign 删表时把端点一并砍掉，前端两处调用只拿到 404
  → 侧边栏永远"暂无求职意向"，而数据其实一直在 L1/L2 里
- PUT 同时补上 Phase 3 遗留的「`source="user"` 没有任何写入方」缺口，
  并验证"用户显式编辑 = 整体替换"（不能被 append 复活）
"""
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.memory.schemas import JobPreference, SessionMemory, UserMemory
from app.memory.service import MemoryService

INTENT_URL = "/api/v1/chat/sessions/{}/intent"


@pytest_asyncio.fixture
async def session_id(authenticated_client):
    """当前测试用户的一个会话"""
    resp = await authenticated_client.post("/api/v1/chat/sessions")
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.fixture
def memory(test_db, tmp_path, monkeypatch):
    """指向 tmp_path 的 MemoryService；同时把 chat 路由里的 base_dir 也换过去

    路由里是 `IntentFileService().base_dir`，不替换会把 L1 markdown 写进真实
    workspace 目录。
    """
    import app.api.v1.chat as chat_module

    monkeypatch.setattr(
        chat_module,
        "IntentFileService",
        lambda *args, **kwargs: SimpleNamespace(base_dir=str(tmp_path)),
    )
    return MemoryService(test_db, base_dir=tmp_path)


async def _current_user(test_db):
    from app.repositories.user_repo import UserRepository

    return await UserRepository(test_db).get_by_username("testuser")


class TestGetSessionIntent:
    @pytest.mark.asyncio
    async def test_empty_memory_returns_null_intent(
        self, authenticated_client, session_id
    ):
        """两边都没有偏好 → intent 为 null，前端保持"暂无求职意向"而不是 404"""
        resp = await authenticated_client.get(INTENT_URL.format(session_id))

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["thread_id"] == session_id
        assert body["intent"] is None

    @pytest.mark.asyncio
    async def test_falls_back_to_l2(self, authenticated_client, test_db, session_id, memory):
        """L1 为空时回落到 L2 长期偏好"""
        user = await _current_user(test_db)
        await memory.write_user_memory(
            user.id,
            UserMemory(
                long_term_preferences=JobPreference(
                    locations=["杭州"], target_roles=["算法实习生"]
                )
            ),
        )

        resp = await authenticated_client.get(INTENT_URL.format(session_id))

        intent = resp.json()["intent"]
        assert intent["locations"] == ["杭州"]
        assert intent["target_roles"] == ["算法实习生"]
        assert intent["filters"] == {}

    @pytest.mark.asyncio
    async def test_l1_wins_per_field(self, authenticated_client, test_db, session_id, memory):
        """本会话改过的城市以 L1 为准，L1 没提的岗位仍回落到 L2"""
        user = await _current_user(test_db)
        await memory.write_user_memory(
            user.id,
            UserMemory(
                long_term_preferences=JobPreference(
                    locations=["杭州"], target_roles=["算法实习生"]
                )
            ),
        )
        await memory.write_session_memory(
            user.id,
            session_id,
            SessionMemory(preferences=JobPreference(locations=["上海"])),
        )

        resp = await authenticated_client.get(INTENT_URL.format(session_id))

        intent = resp.json()["intent"]
        assert intent["locations"] == ["上海"]
        assert intent["target_roles"] == ["算法实习生"]

    @pytest.mark.asyncio
    async def test_invalid_session_id(self, authenticated_client):
        resp = await authenticated_client.get(INTENT_URL.format("not-a-uuid"))
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        resp = await client.get(INTENT_URL.format("00000000-0000-0000-0000-000000000001"))
        assert resp.status_code == 401


class TestPutSessionIntent:
    @pytest.mark.asyncio
    async def test_user_write_replaces_agent_list(
        self, authenticated_client, test_db, session_id, memory
    ):
        """用户显式编辑必须整体覆盖 agent 累加的值，否则删掉的偏好会留着"""
        user = await _current_user(test_db)
        await memory.write_user_memory(
            user.id,
            UserMemory(
                long_term_preferences=JobPreference(locations=["杭州", "深圳"]),
                preference_sources={"locations": "agent"},
            ),
        )

        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"locations": ["北京"]}
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["intent"]["locations"] == ["北京"]

        saved = await memory.get_user_memory(user.id)
        assert saved.long_term_preferences.locations == ["北京"]
        assert saved.preference_sources["locations"] == "user"

    @pytest.mark.asyncio
    async def test_second_user_edit_can_clear(self, authenticated_client, test_db, session_id, memory):
        """同级（user 改 user）也要能清空——只靠优先级比较会退化成 append"""
        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"locations": ["上海"]}
        )
        assert resp.status_code == 200

        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"locations": []}
        )
        assert resp.json()["intent"] is None  # 全空 → null

        user = await _current_user(test_db)
        saved = await memory.get_user_memory(user.id)
        assert saved.long_term_preferences.locations == []

    @pytest.mark.asyncio
    async def test_put_syncs_l1_and_writes_markdown(
        self, authenticated_client, test_db, session_id, memory, tmp_path
    ):
        """PUT 同时写 L1：GET 以 L1 为准，只写 L2 会被旧 L1 盖住；markdown 落盘
        也让该会话之后的冷启动能 read_file 到 L1"""
        user = await _current_user(test_db)
        await memory.write_session_memory(
            user.id,
            session_id,
            SessionMemory(preferences=JobPreference(locations=["广州"])),
        )

        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"locations": ["杭州"]}
        )

        assert resp.json()["intent"]["locations"] == ["杭州"]
        md_path = memory.session_markdown_path(user.id, session_id)
        assert md_path.exists()
        assert "杭州" in md_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_normalizes_and_validates(
        self, authenticated_client, test_db, session_id, memory
    ):
        """trim / 去重 / 招聘类型枚举校验（大小写宽容）"""
        resp = await authenticated_client.put(
            INTENT_URL.format(session_id),
            json={"locations": [" 杭州 ", "杭州", "", "北京"], "recruitment_types": ["intern"]},
        )

        assert resp.status_code == 200, resp.text
        intent = resp.json()["intent"]
        assert intent["locations"] == ["杭州", "北京"]
        assert intent["recruitment_types"] == ["INTERN"]

        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"recruitment_types": ["校招"]}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_body_rejected(self, authenticated_client, session_id):
        resp = await authenticated_client.put(INTENT_URL.format(session_id), json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_salary_round_trip(self, authenticated_client, session_id):
        resp = await authenticated_client.put(
            INTENT_URL.format(session_id),
            json={"salary": {"min": 30000, "max": 40000, "currency": "CNY"}},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["intent"]["salary"]["max"] == 40000

    @pytest.mark.asyncio
    async def test_other_users_session_returns_404(
        self, authenticated_client, test_db, session_id
    ):
        """IDOR：非本人会话统一 404，不泄露存在性"""
        from app.repositories.user_repo import UserRepository
        from app.utils.security import create_access_token

        other = await UserRepository(test_db).create(
            username="otheruser", password="TestPassword123"
        )
        await test_db.commit()
        token = create_access_token(data={"sub": str(other.id)}, expires_delta=None)
        authenticated_client.headers["Authorization"] = f"Bearer {token}"

        resp = await authenticated_client.get(INTENT_URL.format(session_id))
        assert resp.status_code == 404

        resp = await authenticated_client.put(
            INTENT_URL.format(session_id), json={"locations": ["杭州"]}
        )
        assert resp.status_code == 404
