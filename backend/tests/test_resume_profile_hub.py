"""
Tests for resume-profile-hub change:
- Phase 1.1: 解析完成后写回 extracted_content（成功/失败路径）
- Phase 1.2: extract_resume_profile position/title 字段错位修复
- Phase 1.3: 上传路径 active_status 互斥
- Phase 2.2: build_summary 容错构建
- Phase 4.1: PATCH /resumes/{id}/profile section 级合并语义
- 列表 API 返回 summary / is_default
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from unittest.mock import patch, AsyncMock

from app.api.v1.resumes import build_summary, process_resume_async
from app.models import Resume, ResumeAnalysis
from app.schemas import ResumeProfileUpdateRequest
from app.services.query_enhancer import extract_resume_profile
from app.services.resume_upload_service import ResumeUploadService


# ── Phase 1.2: position/title 字段兼容 ──

class TestExtractResumeProfile:
    def test_position_field_used(self):
        """解析 schema 的 work_experience 用 position 字段时能正确提取 latest_title"""
        content = {
            "skills": ["Python", "SQL"],
            "work_experience": [
                {"position": "产品经理", "company": "字节跳动"},
            ],
        }
        profile = extract_resume_profile(content)
        assert profile["latest_title"] == "产品经理"
        assert profile["latest_company"] == "字节跳动"
        assert profile["skills"] == ["Python", "SQL"]

    def test_title_field_fallback(self):
        """旧数据用 title 字段时仍能兼容"""
        content = {
            "work_experience": [
                {"title": "数据分析师", "company": "腾讯"},
            ],
        }
        profile = extract_resume_profile(content)
        assert profile["latest_title"] == "数据分析师"

    def test_empty_content(self):
        assert extract_resume_profile(None) == {}
        assert extract_resume_profile({}) == {}


# ── Phase 2.2: build_summary 容错构建 ──

class TestBuildSummary:
    def test_complete_data(self):
        parsed_data = {
            "work_experience": [{"position": "产品经理", "company": "字节跳动"}],
            "education": [{"degree": "硕士", "school": "清华"}],
            "skills": ["SQL", "Python", "Figma", "用户调研", "A/B测试", "数据分析"],
        }
        evaluation = {
            "dimension_scores": {"completeness": 85},
            "suggestions": [{"issue": "x"}, {"issue": "y"}, {"issue": "z"}],
        }
        summary = build_summary(parsed_data, evaluation)
        assert summary is not None
        assert summary.latest_title == "产品经理"
        assert summary.latest_company == "字节跳动"
        assert summary.highest_degree == "硕士"
        assert summary.skills_preview == ["SQL", "Python", "Figma", "用户调研", "A/B测试"]
        assert summary.completeness == 85
        assert summary.suggestion_count == 3

    def test_broken_parsed_data(self):
        """残缺 parsed_data 不报错，字段一律 None/空"""
        summary = build_summary({"skills": "not-a-list"}, None)
        assert summary is not None
        assert summary.latest_title is None
        assert summary.skills_preview == []
        assert summary.completeness is None
        assert summary.suggestion_count == 0

    def test_no_data(self):
        assert build_summary(None, None) is None
        assert build_summary({}, {}) is None

    def test_title_fallback_in_summary(self):
        """work_experience 只有 title 字段时也兼容"""
        summary = build_summary({"work_experience": [{"title": "工程师"}]}, None)
        assert summary is not None
        assert summary.latest_title == "工程师"


# ── Phase 1.3: 上传路径 active_status 互斥 ──

class TestUploadActiveStatusMutex:
    @pytest.mark.asyncio
    async def test_first_resume_auto_activated(self, test_db):
        """首份简历自动激活"""
        svc = ResumeUploadService()
        user_id = uuid.uuid4()
        resume = await svc.create_resume_record(
            test_db, user_id,
            {"original_filename": "a.pdf", "file_path": "/tmp/a.pdf",
             "file_size": 1, "content_type": "application/pdf"},
        )
        assert resume.active_status is True

    @pytest.mark.asyncio
    async def test_second_resume_not_activated(self, test_db):
        """已有激活简历时，新上传不激活"""
        svc = ResumeUploadService()
        user_id = uuid.uuid4()
        file_info = {"original_filename": "a.pdf", "file_path": "/tmp/a.pdf",
                     "file_size": 1, "content_type": "application/pdf"}
        first = await svc.create_resume_record(test_db, user_id, file_info)
        assert first.active_status is True

        second = await svc.create_resume_record(test_db, user_id, file_info)
        assert second.active_status is False

    @pytest.mark.asyncio
    async def test_model_default_is_false(self):
        """模型层 active_status 默认值应为 False（互斥语义）"""
        from app.models import Resume as ResumeModel
        column = ResumeModel.__table__.columns["active_status"]
        assert column.default is not None
        assert column.default.arg is False


# ── Phase 4.1 + 列表 API 集成测试 ──

async def _create_resume_with_analysis(
    test_db, user_id, *, active_status=False, extracted_content=None,
    parsed_data=None, evaluation=None, analysis_status="completed",
):
    resume = Resume(
        user_id=user_id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_size=1024,
        content_type="application/pdf",
        uploaded_at=datetime.utcnow(),
        active_status=active_status,
        extracted_content=extracted_content,
    )
    test_db.add(resume)
    await test_db.flush()

    analysis = ResumeAnalysis(
        resume_id=resume.id,
        parsed_data=parsed_data,
        evaluation=evaluation,
        status=analysis_status,
    )
    test_db.add(analysis)
    await test_db.commit()
    return resume, analysis


class TestListResumesSummaryAPI:
    @pytest.mark.asyncio
    async def test_list_returns_summary_and_is_default(self, authenticated_client, test_db):
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(test_db)
        user = await user_repo.get_by_username("testuser")

        await _create_resume_with_analysis(
            test_db, user.id,
            active_status=True,
            parsed_data={
                "work_experience": [{"position": "产品经理", "company": "字节跳动"}],
                "education": [{"degree": "硕士"}],
                "skills": ["SQL", "Python"],
            },
            evaluation={"dimension_scores": {"completeness": 80}, "suggestions": [{}]},
        )

        resp = await authenticated_client.get("/api/v1/resumes/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["is_default"] is True
        assert item["summary"] is not None
        assert item["summary"]["latest_title"] == "产品经理"
        assert item["summary"]["latest_company"] == "字节跳动"
        assert item["summary"]["skills_preview"] == ["SQL", "Python"]
        assert item["summary"]["completeness"] == 80
        assert item["summary"]["suggestion_count"] == 1

    @pytest.mark.asyncio
    async def test_list_no_summary_for_pending_analysis(self, authenticated_client, test_db):
        """pending/failed 分析不给摘要"""
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(test_db)
        user = await user_repo.get_by_username("testuser")

        await _create_resume_with_analysis(
            test_db, user.id,
            parsed_data={"skills": ["SQL"]},
            analysis_status="pending",
        )

        resp = await authenticated_client.get("/api/v1/resumes/")
        assert resp.status_code == 200
        assert resp.json()[0]["summary"] is None


class TestPatchResumeProfile:
    @pytest.mark.asyncio
    async def test_partial_section_merge(self, authenticated_client, test_db):
        """未传 section 不动；传入 section 整体替换；打 manually_edited 标记"""
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(test_db)
        user = await user_repo.get_by_username("testuser")

        resume, _ = await _create_resume_with_analysis(
            test_db, user.id,
            extracted_content={
                "skills": ["SQL", "Python"],
                "projects": [{"name": "项目A"}],
                "personal_info": {"name": "张三", "email": "old@a.com"},
            },
        )

        payload = ResumeProfileUpdateRequest(skills=["Java", "Go"]).model_dump(exclude_unset=True)
        resp = await authenticated_client.patch(
            f"/api/v1/resumes/{resume.id}/profile", json=payload
        )
        assert resp.status_code == 200
        merged = resp.json()["extracted_content"]

        # 传入 section 整体替换
        assert merged["skills"] == ["Java", "Go"]
        # 未传 section 不动
        assert merged["projects"] == [{"name": "项目A"}]
        assert merged["personal_info"]["name"] == "张三"
        # 标记
        assert merged["manually_edited"] is True

        # 数据库中已写回
        await test_db.refresh(resume)
        assert resume.extracted_content["skills"] == ["Java", "Go"]

    @pytest.mark.asyncio
    async def test_patch_invalid_uuid_422(self, authenticated_client):
        """非法 UUID → 422（修复前裸抛 ValueError → 500）"""
        resp = await authenticated_client.patch(
            "/api/v1/resumes/not-a-uuid/profile",
            json={"skills": ["Java"]},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_conflict_when_no_extracted_content(self, authenticated_client, test_db):
        """extracted_content 为空 → 409"""
        from app.repositories.user_repo import UserRepository
        user_repo = UserRepository(test_db)
        user = await user_repo.get_by_username("testuser")

        resume, _ = await _create_resume_with_analysis(
            test_db, user.id, extracted_content=None,
        )

        resp = await authenticated_client.patch(
            f"/api/v1/resumes/{resume.id}/profile",
            json={"skills": ["Java"]},
        )
        assert resp.status_code == 409


# ── Phase 1.1: 解析完成后写回 extracted_content ──

def _fake_session_local(test_db):
    """让 process_resume_async 内部的 AsyncSessionLocal() 复用测试 session"""
    @asynccontextmanager
    async def _fake_local():
        yield test_db
    return _fake_local


async def _create_pending_resume(test_db):
    resume = Resume(
        user_id=uuid.uuid4(),
        filename="t.pdf",
        file_path="/tmp/t.pdf",
        file_size=1,
        content_type="application/pdf",
        uploaded_at=datetime.utcnow(),
        active_status=False,
        extracted_content=None,
    )
    test_db.add(resume)
    await test_db.flush()
    analysis = ResumeAnalysis(resume_id=resume.id, parsed_data=None, status="pending")
    test_db.add(analysis)
    await test_db.commit()
    return resume, analysis


PARSED_DATA = {
    "skills": ["SQL", "Python"],
    "work_experience": [{"position": "产品经理", "company": "字节跳动"}],
}
EVALUATION = {"overall_score": 80, "dimension_scores": {"completeness": 85}}


class TestProcessResumeAsyncWriteback:
    """写回链路：解析成功后 extracted_content 非空；失败后保持 NULL"""

    @pytest.mark.asyncio
    async def test_writeback_on_success(self, test_db):
        resume, analysis = await _create_pending_resume(test_db)

        # 只 mock LLM 相关环节，保留 update_analysis_status 等真实 DB 操作
        with patch.object(
            __import__("app.api.v1.resumes", fromlist=["parser_service"]).parser_service,
            "extract_text",
            return_value="resume text",
        ), patch.object(
            __import__("app.api.v1.resumes", fromlist=["parser_service"]).parser_service,
            "parse_with_llm",
            new=AsyncMock(return_value=PARSED_DATA),
        ), patch.object(
            __import__("app.api.v1.resumes", fromlist=["evaluation_service"]).evaluation_service,
            "generate_evaluation_report",
            new=AsyncMock(return_value=EVALUATION),
        ), patch(
            "app.database.AsyncSessionLocal", _fake_session_local(test_db)
        ), patch(
            "app.memory.service.MemoryService"
        ), patch(
            "app.services.preference_extraction_service.PreferenceExtractionService"
        ), patch(
            "app.services.intent_file_service.IntentFileService"
        ):
            await process_resume_async(
                str(resume.id), str(analysis.id), "/tmp/t.pdf", "application/pdf"
            )

        await test_db.refresh(resume)
        await test_db.refresh(analysis)

        # ✅ 核心：解析成功后 extracted_content 非空且等于 parsed_data
        assert resume.extracted_content == PARSED_DATA
        assert resume.parsed_at is not None
        assert analysis.status == "completed"

    @pytest.mark.asyncio
    async def test_no_writeback_on_failure(self, test_db):
        """status=failed 不写回，extracted_content 保持 NULL"""
        resume, analysis = await _create_pending_resume(test_db)

        with patch.object(
            __import__("app.api.v1.resumes", fromlist=["parser_service"]).parser_service,
            "extract_text",
            side_effect=Exception("boom"),
        ), patch(
            "app.database.AsyncSessionLocal", _fake_session_local(test_db)
        ):
            # 内部吞异常，不应向外抛
            await process_resume_async(
                str(resume.id), str(analysis.id), "/tmp/t.pdf", "application/pdf"
            )

        await test_db.refresh(resume)
        await test_db.refresh(analysis)

        # ✅ 失败路径：extracted_content 保持 NULL
        assert resume.extracted_content is None
        assert resume.parsed_at is None
        assert analysis.status == "failed"
