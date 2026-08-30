"""reparse 限次与上传大小上限单测（api-abuse-protection Phase 5.2 / 5.4）。

- reparse：同 resume 第 4 次 → 429；仅首次设 TTL（1 小时固定窗口）；Redis 降级放行
- 上传大小：超过 RESUME_MAX_FILE_MB → 413（复用 resume_upload_service 既有 413 校验）
"""

import uuid

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, Mock

from app.api.v1.resumes import _check_reparse_quota
from app.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
class TestReparseQuota:

    async def test_first_three_allowed(self, fake_redis):
        resume_id = uuid.uuid4()
        for _ in range(settings.REPARSE_HOURLY_LIMIT):
            await _check_reparse_quota(resume_id)  # 不抛

    async def test_fourth_reparse_429(self, fake_redis):
        """同 resume 第 4 次 → 429"""
        resume_id = uuid.uuid4()
        for _ in range(settings.REPARSE_HOURLY_LIMIT):
            await _check_reparse_quota(resume_id)
        with pytest.raises(HTTPException) as exc_info:
            await _check_reparse_quota(resume_id)
        assert exc_info.value.status_code == 429

    async def test_counter_key_has_ttl(self, fake_redis):
        """仅首次 INCR 设 TTL：1 小时固定窗口"""
        resume_id = uuid.uuid4()
        await _check_reparse_quota(resume_id)
        ttl = await fake_redis.ttl(f"reparse:{resume_id}")
        assert 0 < ttl <= 3600

    async def test_different_resumes_independent(self, fake_redis):
        a, b = uuid.uuid4(), uuid.uuid4()
        for _ in range(settings.REPARSE_HOURLY_LIMIT):
            await _check_reparse_quota(a)
        await _check_reparse_quota(b)  # 另一份简历不受影响

    async def test_degrades_open_when_redis_down(self, broken_redis):
        """Redis 不可用 → 放行"""
        await _check_reparse_quota(uuid.uuid4())  # 不抛


@pytest.mark.asyncio
class TestResumeUploadSizeLimit:

    async def test_oversized_file_413(self):
        """超过 RESUME_MAX_FILE_MB 的文件 → 413（save_file 既有校验，size 与流式双重检查）"""
        from app.services.resume_upload_service import ResumeUploadService

        service = ResumeUploadService()
        max_bytes = service.MAX_FILE_SIZE

        mock_file = Mock()
        mock_file.filename = "big.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = max_bytes + 1

        with pytest.raises(HTTPException) as exc_info:
            await service.save_file(mock_file, uuid.uuid4())
        assert exc_info.value.status_code == 413

    async def test_streamed_oversized_file_413(self):
        """file.size 缺失但内容超限（流式绕过）→ 读取后仍 413"""
        from app.services.resume_upload_service import ResumeUploadService

        service = ResumeUploadService()
        max_bytes = service.MAX_FILE_SIZE

        mock_file = Mock()
        mock_file.filename = "big.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = None  # 伪装：size 元信息缺失
        mock_file.read = AsyncMock(return_value=b"x" * (max_bytes + 1))

        with pytest.raises(HTTPException) as exc_info:
            await service.save_file(mock_file, uuid.uuid4())
        assert exc_info.value.status_code == 413
