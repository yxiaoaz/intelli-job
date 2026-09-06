# -*- coding: utf-8 -*-
"""Lever spider（ats-job-source-integration Phase 2.2）。

端点：GET https://api.lever.co/v0/postings/{slug}?mode=json
**响应是裸数组**（无 jobs 包裹，禁止 .get("jobs")）；createdAt 为 epoch 毫秒；
探活实测延迟 55~61s，DOWNLOAD_TIMEOUT=120。
"""
import logging
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from scrapy import Request

from app.models.constants import JobSource, RecruitmentType
from job_crawler.base_spider import BaseJobSpider, load_verified_boards
from job_crawler.contracts import FetchState, NormalizedJob

logger = logging.getLogger(__name__)


def _recruitment_type_from_commitment(commitment: str) -> RecruitmentType:
    """实测值域 Full-time/Fixed Term/Contract；含 Intern→INTERN。"""
    if "intern" in (commitment or "").lower():
        return RecruitmentType.INTERN
    return RecruitmentType.EXPERIENCED


class LeverSpider(BaseJobSpider):
    name = "lever-spider"
    job_source = JobSource.LEVER

    custom_settings = {
        # 探活实测 55~61s 延迟，全局超时会误伤其他源，per-spider 覆盖
        "DOWNLOAD_TIMEOUT": 120,
    }

    def start_requests(self):
        boards = load_verified_boards("lever")
        if not boards:
            logger.warning("[%s] 注册表无 VERIFIED board，本次不爬取", self.name)
            return
        for board in boards:
            url = f"https://api.lever.co/v0/postings/{board['board_slug']}?mode=json"
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

        # 裸数组：isinstance(list) 判断，禁止 .get("jobs")
        jobs = data if isinstance(data, list) else []

        count = 0
        for raw in jobs:
            for job in self.normalize(raw):
                yield self._to_item(job)
                count += 1
        self.note_parse_result(response, count)

    def normalize(self, raw) -> NormalizedJob:
        """Lever posting dict → NormalizedJob。"""
        # createdAt：epoch 毫秒 → aware UTC datetime
        published_at = None
        if raw.get("createdAt"):
            published_at = datetime.fromtimestamp(
                raw["createdAt"] / 1000, tz=timezone.utc)

        # descriptionPlain 已是纯文本（实测覆盖 96%），空则回退 description 剥 HTML
        description = raw.get("descriptionPlain") or ""
        if not description and raw.get("description"):
            description = BeautifulSoup(raw["description"], "html.parser")\
                .get_text(separator="\n", strip=True)

        # salaryRange → 结构化 min/max + 展示文本（双形态并存）
        salary = None
        salary_min = salary_max = None
        salary_range = raw.get("salaryRange") or {}
        if salary_range.get("min") is not None \
                and salary_range.get("max") is not None:
            salary_min = int(salary_range["min"])
            salary_max = int(salary_range["max"])
            currency = salary_range.get("currency") or ""
            salary = f"{currency} {salary_min} – {salary_max}"

        categories = raw.get("categories") or {}

        yield NormalizedJob(
            source=JobSource.LEVER,
            source_url=raw.get("hostedUrl") or "",
            external_id=str(raw.get("id") or ""),
            company_name=raw.get("company_name") or "",
            job_title=raw.get("text") or "",  # Lever 用 text 表示职位名
            location=categories.get("location") or "",
            salary=salary,
            salary_min=salary_min,
            salary_max=salary_max,
            recruitment_type=_recruitment_type_from_commitment(
                categories.get("commitment") or ""),
            published_at=published_at,
            update_time=datetime.now(),
            description=description,
        )
