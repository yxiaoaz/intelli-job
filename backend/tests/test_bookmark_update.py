"""
PATCH /api/v1/jobs/bookmarks/{job_id} 单测

覆盖：只改 status / 只改 notes / 同时改 / 传空串清空 notes / 404 / 非法 status 422 / notes 超长 422
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobItem, User
from app.models.constants import JobSource, RecruitmentType
from app.repositories.job_repo import BookmarkRepository


async def _create_job(db: AsyncSession) -> JobItem:
    """在测试库中创建一个可被收藏的职位（标题/公司不能是"未知"，否则 get_by_id 会排除）"""
    suffix = uuid.uuid4().hex
    job = JobItem(
        source=JobSource.ZHILIAN,
        url=f"https://example.com/job/{suffix}",
        fingerprint=f"fp-{suffix}",
        job_title="数据分析师",
        company_name="字节跳动",
        location="北京",
        recruitment_type=RecruitmentType.GRADUATE,
        description="测试职位描述",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _create_bookmark(db: AsyncSession, user: User, job: JobItem):
    bookmark_repo = BookmarkRepository(db)
    bookmark = await bookmark_repo.create(user.id, job.id)
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


async def _get_test_user(db: AsyncSession) -> User:
    """authenticated_client fixture 创建的用户"""
    result = await db.execute(select(User).where(User.username == "testuser"))
    return result.scalar_one()


@pytest.fixture
async def bookmarked_job(test_db, authenticated_client):
    """为已认证用户准备一个已收藏的职位，返回 (job, bookmark)"""
    user = await _get_test_user(test_db)
    job = await _create_job(test_db)
    bookmark = await _create_bookmark(test_db, user, job)
    return job, bookmark


class TestUpdateBookmark:
    """PATCH /bookmarks/{job_id}"""

    @pytest.mark.asyncio
    async def test_update_status_only(self, client, test_db, bookmarked_job):
        """只改 status：notes 不受影响"""
        job, _ = bookmarked_job
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"status": "applied"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applied"
        assert data["notes"] is None

    @pytest.mark.asyncio
    async def test_update_notes_only(self, client, test_db, bookmarked_job):
        """只改 notes：status 保持 saved 不变"""
        job, _ = bookmarked_job
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"notes": "已找内推"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["notes"] == "已找内推"

    @pytest.mark.asyncio
    async def test_update_status_and_notes(self, client, test_db, bookmarked_job):
        """同时改 status 和 notes"""
        job, _ = bookmarked_job
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"status": "interviewing", "notes": "周二一面"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "interviewing"
        assert data["notes"] == "周二一面"

    @pytest.mark.asyncio
    async def test_clear_notes_with_empty_string(self, client, test_db, bookmarked_job):
        """传空串清空 notes（约定：None = 不修改，空串 = 清空）"""
        job, _ = bookmarked_job
        # 先写入备注
        r1 = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"notes": "旧备注"},
        )
        assert r1.status_code == 200
        # 再传空串清空
        r2 = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"notes": ""},
        )
        assert r2.status_code == 200
        assert r2.json()["notes"] == ""

    @pytest.mark.asyncio
    async def test_update_nonexistent_bookmark_404(self, authenticated_client):
        """收藏不存在时返回 404"""
        response = await authenticated_client.patch(
            f"/api/v1/jobs/bookmarks/{uuid.uuid4()}",
            json={"status": "applied"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_status_422(self, client, test_db, bookmarked_job):
        """非法 status 值由 Pydantic 枚举校验拦截，返回 422"""
        job, _ = bookmarked_job
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"status": "bogus-status"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_notes_too_long_422(self, client, test_db, bookmarked_job):
        """notes 超过 2000 字符返回 422"""
        job, _ = bookmarked_job
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{job.id}",
            json={"notes": "x" * 2001},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_requires_auth(self, client):
        """未认证请求返回 401"""
        response = await client.patch(
            f"/api/v1/jobs/bookmarks/{uuid.uuid4()}",
            json={"status": "applied"},
        )
        assert response.status_code == 401
