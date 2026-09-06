"""ATS 三源解析器单测（ats-job-source-integration tasks 2.1/2.2/2.3）。

以 fixtures 真实样本驱动（不联网），覆盖 design §1 的字段映射与坑位规则。
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.constants import AcademicQualification, RecruitmentType
from job_crawler.spiders.greenhouse_spider import (
    GreenhouseSpider, _recruitment_type_from_title)
from job_crawler.spiders.lever_spider import (
    LeverSpider, _recruitment_type_from_commitment)
from job_crawler.spiders.ashby_spider import AshbySpider, _extract_salary

FIXTURES = Path(__file__).resolve().parents[2] / "job_crawler" / "fixtures"


def _load(*parts):
    return json.loads((FIXTURES.joinpath(*parts)).read_text(encoding="utf-8"))


def _one(spider_cls, raw):
    spider = spider_cls.__new__(spider_cls)
    spider.name = spider_cls.name
    return list(spider.normalize(raw))[0]


# ── Greenhouse ─────────────────────────────────────────────────────────────

class TestGreenhouseParser:
    @pytest.fixture()
    def job(self):
        raw = _load("greenhouse", "stripe-jobs.json")["jobs"][0]
        return _one(GreenhouseSpider, raw)

    def test_title_and_location(self, job):
        assert job.job_title == "Abuse Investigator"
        assert job.location == "Dublin"

    def test_company_name(self, job):
        assert job.company_name == "Stripe"

    def test_published_at_iso(self, job):
        """first_published ISO 8601 直存（带时区）。"""
        assert job.published_at == datetime.fromisoformat(
            "2026-09-03T13:32:53-04:00")

    def test_education_placeholder_falls_to_all(self, job):
        """education 值为占位 education_required → ALL（未知值落 ALL）。"""
        assert job.min_academic_qualification is AcademicQualification.ALL

    def test_recruitment_type_from_title(self, job):
        assert job.recruitment_type is RecruitmentType.EXPERIENCED

    @pytest.mark.parametrize("title,expected", [
        ("Data Science Intern", RecruitmentType.INTERN),
        ("University Graduate 2027", RecruitmentType.GRADUATE),
        ("Software Engineer", RecruitmentType.EXPERIENCED),
    ])
    def test_title_keywords(self, title, expected):
        assert _recruitment_type_from_title(title) is expected

    def test_description_html_stripped(self):
        """content=true 的 HTML 剥标签为纯文本。"""
        raw = {"title": "T", "content": "<h1>Hello</h1><p>World</p>",
               "location": {"name": "X"}}
        job = _one(GreenhouseSpider, raw)
        assert job.description == "Hello\nWorld"


# ── Lever ──────────────────────────────────────────────────────────────────

class TestLeverParser:
    @pytest.fixture()
    def jobs(self):
        postings = _load("lever", "matchgroup-jobs.json")
        return [_one(LeverSpider, p) for p in postings]

    def test_salary_range_structured_and_text(self, jobs):
        """salaryRange.min/max → 结构化 min/max；文本双形态并存。"""
        android = next(j for j in jobs if j.job_title == "Android Engineer III")
        assert android.salary_min == 150000
        assert android.salary_max == 180000
        assert android.salary == "USD 150000 – 180000"
        assert android.salary_min is not None

    def test_created_at_epoch_ms(self, jobs):
        """createdAt epoch 毫秒 → aware UTC。"""
        accountant = jobs[0]  # createdAt: 1787203369315
        assert accountant.published_at == datetime.fromtimestamp(
            1787203369315 / 1000, tz=timezone.utc)

    def test_commitment_mapping(self, jobs):
        accountant = jobs[0]  # commitment: Contract
        assert accountant.recruitment_type is RecruitmentType.EXPERIENCED
        android = next(j for j in jobs if j.job_title == "Android Engineer III")
        assert android.recruitment_type is RecruitmentType.EXPERIENCED

    def test_description_plain_first(self, jobs):
        """descriptionPlain 覆盖 96%，优先使用。"""
        android = next(j for j in jobs if j.job_title == "Android Engineer III")
        assert "Android" in android.description

    def test_location_from_categories(self, jobs):
        android = next(j for j in jobs if j.job_title == "Android Engineer III")
        assert android.location == "New York, New York"

    def test_intern_commitment(self):
        assert _recruitment_type_from_commitment("Intern") is RecruitmentType.INTERN

    def test_text_is_title(self, jobs):
        """Lever 用 text 字段表示职位名。"""
        assert jobs[0].job_title.startswith("Accountant")


# ── Ashby ──────────────────────────────────────────────────────────────────

class TestAshbyParser:
    @pytest.fixture()
    def job(self):
        raw = _load("ashby", "ramp-jobs.json")[0]
        return _one(AshbySpider, raw)

    def test_title_stripped(self, job):
        assert job.job_title == "Security Engineer, Cloud"  # 原始带前导空格

    def test_salary_down_to_tiers(self, job):
        """薪资下沉到 compensationTiers 的 Salary 组件（211400/290600）。"""
        assert job.salary_min == 211400
        assert job.salary_max == 290600
        assert job.salary and "$211.4K" in job.salary

    def test_is_remote_location(self, job):
        assert job.location == "Remote"

    def test_published_at(self, job):
        assert job.published_at == datetime.fromisoformat(
            "2026-04-07T17:12:35.753+00:00")

    def test_employment_type(self, job):
        assert job.recruitment_type is RecruitmentType.EXPERIENCED

    def test_linear_empty_shell_no_salary(self):
        """linear 型空壳：compensation 键存在但 tiers/summaryComponents 全空。"""
        raw = _load("ashby", "linear-jobs.json")[0]
        salary, salary_min, salary_max = _extract_salary(raw)
        assert salary is None
        assert salary_min is None
        assert salary_max is None

    def test_no_compensation_key(self):
        assert _extract_salary({}) == (None, None, None)


# ── 跨源去重（ats Phase 4） ────────────────────────────────────────────────

class TestCrossSourceDedup:
    def test_same_job_two_boards_same_fingerprint(self):
        """同公司同岗同地在两个 board/源重复出现 → 指纹一致。"""
        from job_crawler.contracts import compute_fingerprint

        gh_raw = {"title": "Software Engineer",
                  "company_name": "Stripe",
                  "location": {"name": "Dublin"}}
        lever_raw = {"text": "Software Engineer",
                     "company_name": "Stripe",
                     "categories": {"location": "Dublin"}}
        gh_job = _one(GreenhouseSpider, gh_raw)
        lever_job = _one(LeverSpider, lever_raw)
        assert gh_job.company_name == lever_job.company_name == "Stripe"
        assert compute_fingerprint(gh_job.company_name, gh_job.job_title,
                                   gh_job.location) == \
            compute_fingerprint(lever_job.company_name, lever_job.job_title,
                                lever_job.location)
