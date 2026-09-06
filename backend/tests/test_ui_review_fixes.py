# -*- coding: utf-8 -*-
"""UI 评审（ui-review）后端修复回归测试。

覆盖：
1. update_session_memory 偏好归一化（中文枚举 → schema 合法值）— P0-3
2. chat messages 接口 created_at 带 'Z' 后缀（UTC 时区）— P2-13
3. 简历解析完成后自动激活（互斥）— P0-2
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.agents.conversation_agent import _normalize_preference_updates
from app.models import ChatMessage, Resume


# ═══════════════════════════════════════════════════════
# 1. 偏好归一化（P0-3）
# ═══════════════════════════════════════════════════════

class TestNormalizePreferenceUpdates:
    def test_chinese_recruitment_type_mapped(self):
        updates = {"preferences": {"recruitment_types": ["实习"]}}
        normalized, dropped = _normalize_preference_updates(updates)
        assert normalized["preferences"]["recruitment_types"] == ["INTERN"]
        assert dropped == []

    def test_case_insensitive_and_dedupe(self):
        updates = {"preferences": {"recruitment_types": ["Intern", "INTERN", "校招"]}}
        normalized, _ = _normalize_preference_updates(updates)
        assert normalized["preferences"]["recruitment_types"] == ["GRADUATE", "INTERN"]

    def test_unrecognized_values_dropped(self):
        updates = {"preferences": {"recruitment_types": ["自由职业"]}}
        normalized, dropped = _normalize_preference_updates(updates)
        assert "recruitment_types" not in normalized["preferences"]
        assert dropped == ["preferences.recruitment_types"]

    def test_location_suffix_stripped(self):
        updates = {"preferences": {"locations": ["北京市", "深圳"]}}
        normalized, _ = _normalize_preference_updates(updates)
        assert normalized["preferences"]["locations"] == ["北京", "深圳"]

    def test_non_dict_preferences_passthrough(self):
        updates = {"current_goal": "找实习"}
        normalized, dropped = _normalize_preference_updates(updates)
        assert normalized == updates
        assert dropped == []


# ═══════════════════════════════════════════════════════
# 2. messages 接口 created_at 带 Z 后缀（P2-13）
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_messages_created_at_has_utc_suffix(authenticated_client, test_db):
    """历史消息 created_at 必须带 'Z' 后缀，否则前端按本地时间解析差 8 小时"""
    from app.utils.security import create_access_token  # noqa: F401  确保 app 已初始化

    # 创建会话
    session_resp = await authenticated_client.post("/api/v1/chat/sessions")
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]

    # 直接落库一条消息（模拟历史数据）
    test_db.add(
        ChatMessage(
            session_id=uuid.UUID(session_id),
            role="user",
            content="你好",
        )
    )
    await test_db.commit()

    resp = await authenticated_client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) == 1
    assert messages[0]["created_at"].endswith("Z")


# ═══════════════════════════════════════════════════════
# 3. 简历解析完成后自动激活（P0-2）
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_parsed_resume_auto_activates_and_deactivates_old(
    authenticated_client, test_db, test_engine
):
    """第二份简历解析成功后自动激活，旧的活跃简历失活（互斥）"""
    from app.models import User

    # 找到 authenticated_client 创建的用户
    result = await test_db.execute(select(User).where(User.username == "testuser"))
    user = result.scalar_one()
    user_id = user.id

    # 两份简历：A 激活（旧），B 未激活（新上传）
    resume_a = Resume(
        user_id=user_id,
        filename="old.pdf",
        file_path="/tmp/old.pdf",
        file_size=1024,
        content_type="application/pdf",
        resume_name="old.pdf",
        active_status=True,
    )
    resume_b = Resume(
        user_id=user_id,
        filename="new.pdf",
        file_path="/tmp/new.pdf",
        file_size=1024,
        content_type="application/pdf",
        resume_name="new.pdf",
        active_status=False,
    )
    test_db.add_all([resume_a, resume_b])
    await test_db.commit()
    resume_b_id = resume_b.id
    resume_a_id = resume_a.id

    parsed_data = {"skills": ["Python"], "work_experience": [], "education": []}

    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    mock_parser = MagicMock()
    mock_parser.extract_text = MagicMock(return_value="text content")
    mock_parser.parse_with_llm = AsyncMock(return_value=parsed_data)
    mock_parser.update_analysis_status = AsyncMock()

    mock_evaluation = MagicMock()
    mock_evaluation.generate_evaluation_report = AsyncMock(
        return_value={"dimension_scores": {}, "suggestions": []}
    )
    mock_evaluation.update_analysis_with_evaluation = AsyncMock()

    with patch("app.database.AsyncSessionLocal", test_session_maker), \
            patch("app.api.v1.resumes.parser_service", mock_parser), \
            patch("app.api.v1.resumes.evaluation_service", mock_evaluation), \
            patch("app.services.preference_extraction_service.PreferenceExtractionService") as mock_pref_cls:
        mock_pref_cls.return_value.extract = AsyncMock(return_value=None)

        from app.api.v1.resumes import process_resume_async
        await process_resume_async(
            str(resume_b_id),
            str(uuid.uuid4()),
            "/tmp/new.pdf",
            "application/pdf",
        )

    # 重新查询（绕过 identity map）
    fresh = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with fresh() as check_db:
        a = (await check_db.execute(
            select(Resume).where(Resume.id == resume_a_id)
        )).scalar_one()
        b = (await check_db.execute(
            select(Resume).where(Resume.id == resume_b_id)
        )).scalar_one()

    assert a.active_status is False, "旧活跃简历应被互斥失活"
    assert b.active_status is True, "新解析完成的简历应自动激活"
