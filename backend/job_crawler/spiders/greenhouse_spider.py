# -*- coding: utf-8 -*-
"""Greenhouse spider（ats-job-source-integration Phase 2.1）。

端点：GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
一次拉全含 description（单板 4.6MB，按 board 串行）；字段映射见
openspec/changes/ats-job-source-integration/design.md §1。
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from scrapy import Request

from app.models.constants import AcademicQualification, JobSource, RecruitmentType
from job_crawler.base_spider import BaseJobSpider, load_verified_boards
from job_crawler.contracts import FetchState, NormalizedJob

logger = logging.getLogger(__name__)

# 学历关键词 → AcademicQualification（未知值落 ALL 并记日志）
_EDUCATION_MAP = [
    ("master", AcademicQualification.MASTERS),
    ("postgraduate", AcademicQualification.MASTERS),
    ("bachelor", AcademicQualification.UNDERGRADUATE),
    ("undergraduate", AcademicQualification.UNDERGRADUATE),
    ("associate", AcademicQualification.ASSOCIATE),
    ("phd", AcademicQualification.DOCTOR),
    ("doctor", AcademicQualification.DOCTOR),
]


def _recruitment_type_from_title(title: str) -> RecruitmentType:
    t = (title or "").lower()
    if "intern" in t:
        return RecruitmentType.INTERN
    if any(kw in t for kw in ("university", "new grad", "graduate", "campus")):
        return RecruitmentType.GRADUATE
    return RecruitmentType.EXPERIENCED


class GreenhouseSpider(BaseJobSpider):
    name = "greenhouse-spider"
    job_source = JobSource.GREENHOUSE

    custom_settings = {
        # content=true 单板 4.6MB（探活实测），按 board 串行、放宽超时
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def start_requests(self):
        boards = load_verified_boards("greenhouse")
        if not boards:
            logger.warning("[%s] 注册表无 VERIFIED board，本次不爬取", self.name)
            return
        for board in boards:
            url = (f"https://boards-api.greenhouse.io/v1/boards/"
                   f"{board['board_slug']}/jobs?content=true")
            yield Request(
                url, callback=self.parse_board,
                cb_kwargs={"slug": board["board_slug"],
                           "company_name": board["company_name"]},
                errback=self.on_fetch_error,
            )

    def parse_board(self, response, slug, company_name):
        state, data = self.fetch_json(response)
        if state is FetchState.NO_BOARD:
            self.mark_no_board(slug)
            return
        if state is not FetchState.OK or not isinstance(data, dict):
            return

        count = 0
        for raw in data.get("jobs", []):
            for job in self.normalize(raw):
                yield self._to_item(job)
                count += 1
        self.note_parse_result(response, count)

    def normalize(self, raw) -> NormalizedJob:
        """Greenhouse job dict → NormalizedJob。"""
        # location：location.name（实测覆盖 100%）
        location = (raw.get("location") or {}).get("name") or ""

        # published_at：first_published ISO 8601 直存
        published_at = None
        if raw.get("first_published"):
            try:
                published_at = datetime.fromisoformat(raw["first_published"])
            except ValueError:
                logger.debug("[%s] bad first_published: %s", self.name,
                             raw["first_published"])

        update_time = datetime.now()
        if raw.get("updated_at"):
            try:
                update_time = datetime.fromisoformat(raw["updated_at"])
            except ValueError:
                pass

        # description：content=true 时为 HTML，需剥标签
        description = ""
        if raw.get("content"):
            description = BeautifulSoup(raw["content"], "html.parser")\
                .get_text(separator="\n", strip=True)

        # 学历：education 字段，未知值落 ALL 并记日志
        min_academic_qualification = AcademicQualification.ALL
        education = (raw.get("education") or "").lower()
        for keyword, qualification in _EDUCATION_MAP:
            if keyword in education:
                min_academic_qualification = qualification
                break
        else:
            if education and education != "education_required":
                logger.debug("[%s] unknown education value: %s", self.name,
                             raw.get("education"))

        yield NormalizedJob(
            source=JobSource.GREENHOUSE,
            source_url=raw.get("absolute_url") or "",
            external_id=str(raw.get("id") or ""),
            company_name=raw.get("company_name") or "",
            job_title=raw.get("title") or "",
            location=location,
            salary=None,  # 标题内薪资 0%（实测），不解析
            recruitment_type=_recruitment_type_from_title(raw.get("title") or ""),
            min_academic_qualification=min_academic_qualification,
            published_at=published_at,
            update_time=update_time,
            description=description,
        )
