# -*- coding: utf-8 -*-
"""Ashby spider（ats-job-source-integration Phase 2.3）。

端点：GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
关键坑（探活实测）：`compensation` 键存在 ≠ 有值——linear 键覆盖 100% 但内容全空，
解析必须下沉到 `compensationTiers`/`summaryComponents` 非空才算有薪资。
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from scrapy import Request

from app.models.constants import JobSource, RecruitmentType
from job_crawler.base_spider import BaseJobSpider, load_verified_boards
from job_crawler.contracts import FetchState, NormalizedJob

logger = logging.getLogger(__name__)


def _recruitment_type_from_employment(employment_type: str) -> RecruitmentType:
    """值域含 FULL_TIME 等；含 INTERN→INTERN，否则 EXPERIENCED。"""
    if "intern" in (employment_type or "").lower():
        return RecruitmentType.INTERN
    return RecruitmentType.EXPERIENCED


def _extract_salary(raw: dict) -> tuple[str | None, int | None, int | None]:
    """compensation 下沉判断：tiers/summaryComponents 非空才算有薪资。

    salary_min/max 取各 tier 内 Salary 组件的 minValue/min 与 maxValue/max；
    salary 展示文本取 compensationTierSummary（如 "$211.4K – $290.6K • Offers Equity"）。
    """
    comp = raw.get("compensation") or {}
    tiers = comp.get("compensationTiers") or []
    summary_components = comp.get("summaryComponents") or []
    if not tiers and not summary_components:
        return None, None, None  # linear 型空壳：键存值空

    mins, maxs = [], []
    for tier in tiers:
        for component in (tier.get("components") or []):
            if component.get("compensationType") == "Salary":
                if component.get("minValue") is not None:
                    mins.append(int(component["minValue"]))
                if component.get("maxValue") is not None:
                    maxs.append(int(component["maxValue"]))

    salary_min = min(mins) if mins else None
    salary_max = max(maxs) if maxs else None
    salary_text = comp.get("compensationTierSummary") or None
    return salary_text, salary_min, salary_max


class AshbySpider(BaseJobSpider):
    name = "ashby-spider"
    job_source = JobSource.ASHBY

    def start_requests(self):
        boards = load_verified_boards("ashby")
        if not boards:
            logger.warning("[%s] 注册表无 VERIFIED board，本次不爬取", self.name)
            return
        for board in boards:
            url = (f"https://api.ashbyhq.com/posting-api/job-board/"
                   f"{board['board_slug']}?includeCompensation=true")
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
        if state is not FetchState.OK:
            return

        # 实测响应为 {"jobs": [...]}；裸数组样本亦可兼容
        if isinstance(data, dict):
            jobs = data.get("jobs", [])
        elif isinstance(data, list):
            jobs = data
        else:
            jobs = []

        count = 0
        for raw in jobs:
            for job in self.normalize(raw):
                yield self._to_item(job)
                count += 1
        self.note_parse_result(response, count)

    def normalize(self, raw) -> NormalizedJob:
        """Ashby job dict → NormalizedJob。"""
        # location + isRemote：remote=True 时 location 置 Remote
        location = raw.get("location") or ""
        if raw.get("isRemote"):
            location = "Remote"

        # publishedAt ISO
        published_at = None
        if raw.get("publishedAt"):
            try:
                published_at = datetime.fromisoformat(raw["publishedAt"])
            except ValueError:
                logger.debug("[%s] bad publishedAt: %s", self.name,
                             raw["publishedAt"])

        salary, salary_min, salary_max = _extract_salary(raw)

        yield NormalizedJob(
            source=JobSource.ASHBY,
            source_url=raw.get("jobUrl") or "",
            external_id=str(raw.get("id") or ""),
            company_name=raw.get("company_name") or "",
            job_title=(raw.get("title") or "").strip(),
            location=location,
            salary=salary,
            salary_min=salary_min,
            salary_max=salary_max,
            recruitment_type=_recruitment_type_from_employment(
                raw.get("employmentType") or ""),
            published_at=published_at,
            update_time=datetime.now(),
            description=raw.get("descriptionPlain")
            or BeautifulSoup(raw.get("descriptionHtml") or "",
                             "html.parser").get_text(separator="\n", strip=True),
        )
