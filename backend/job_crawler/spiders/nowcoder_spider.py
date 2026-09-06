# -*- coding: utf-8 -*-
"""牛客网 spider（nowcoder-spider Phase 3.1）。

端点（探活实测 2026-09-06，见 docs/data-sources/probe-report-2026-09-06.md 六）：
- 公司枚举  GET gw-c.nowcoder.com/api/sparta/one-delivery-company/list?page&pageSize
- 公司岗位  GET gw-c.nowcoder.com/api/sparta/one-delivery-job/job-list?companyId&page&pageSize

关键实测坑：
1. company/list 的 records_len < pageSize（服务端折扣 100→95/200→187）——
   翻页以 totalPage 为准，不得假设 records_len == pageSize；
2. 200 包裹体 `success:false` 是业务错误； companyId 缺失返回 400 Spring 风格错误；
3. source_url 冻结为 job-detail API 拼 URL（决策 4b）：jobDetailUrl 为 null 且
   web 路由不可跳转，但 detail API 可 GET 回溯。

失败隔离（决策 5/6）：
- 公司枚举失败 → CloseSpider 中止整轮（fetch_state 保持 FETCH_FAILED）；
- 单公司岗位失败（HTTP 错误 / success:false / 解析失败）→ 仅 warning 跳过，
  不触碰 fetch_state（收口语义：单公司失败不进健康度）。
"""
import json
import logging
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from scrapy import Request
from scrapy.exceptions import CloseSpider

from app.models.constants import JobSource, RecruitmentType
from job_crawler.base_spider import BaseJobSpider
from job_crawler.contracts import FetchState, NormalizedJob

logger = logging.getLogger(__name__)

NOWCODER_API_BASE = "https://gw-c.nowcoder.com/api/sparta"
COMPANY_LIST_URL = f"{NOWCODER_API_BASE}/one-delivery-company/list"
JOB_LIST_URL = f"{NOWCODER_API_BASE}/one-delivery-job/job-list"
# source_url 冻结拼法（决策 4b）：job-detail API，可 GET 回溯（200+完整 JD）
JOB_DETAIL_URL_TPL = f"{NOWCODER_API_BASE}/one-delivery-job/job-detail?companyId={{company_id}}&jobId={{job_id}}"

COMPANY_PAGE_SIZE = 200  # 1.2 实测冻结：totalPage 翻页，records 折扣不影响正确性
JOB_PAGE_SIZE = 100      # 1.2 实测生效


def recruitment_type_from_title(title: str) -> RecruitmentType:
    """1.3 实测无权威来源（参数无效/端点 404），冻结按标题推断。

    牛客以校招实习为主：含 intern/实习 → INTERN，否则 GRADUATE
    （不做 EXPERIENCED 推断）。
    """
    lowered = (title or "").lower()
    if "intern" in lowered or "实习" in (title or ""):
        return RecruitmentType.INTERN
    return RecruitmentType.GRADUATE


def parse_salary(raw: dict) -> tuple[str | None, int | None, int | None]:
    """minSalary/maxSalary 单位 k/月（如 41.7）→ 人民币月薪（元），×1000。

    "·12薪"年薪倍数不折算进列（列语义 = 月薪区间，决策 3）；
    原始展示文本直存 salary 列。
    """
    salary_min = salary_max = None
    try:
        if raw.get("minSalary") is not None:
            salary_min = round(float(raw["minSalary"]) * 1000)
        if raw.get("maxSalary") is not None:
            salary_max = round(float(raw["maxSalary"]) * 1000)
    except (TypeError, ValueError):
        logger.debug("[nowcoder-spider] bad salary fields: %s/%s",
                     raw.get("minSalary"), raw.get("maxSalary"))
    salary_text = raw.get("salary") or None
    return salary_text, salary_min, salary_max


class NowcoderSpider(BaseJobSpider):
    name = "nowcoder-spider"
    job_source = JobSource.NOWCODER

    custom_settings = {
        # 1.1 实测 0.5s 间隔零拦截；并发压到 1 保证聚合速率 ≈ 2 req/s
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_MAX_DELAY": 5,
    }

    def __init__(self, company_limit: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 本地试跑/限流用：只枚举前 N 家公司（tasks 3.4 前 20 公司）
        self.company_limit = int(company_limit) if company_limit else None
        self._companies: list[tuple[int, str]] = []

    # ── 公司枚举（决策 1：运行时动态获取，不进 registry）────────────────────

    def start_requests(self):
        yield Request(
            f"{COMPANY_LIST_URL}?page=1&pageSize={COMPANY_PAGE_SIZE}",
            callback=self.parse_companies,
            cb_kwargs={"page": 1},
            errback=self.on_enumeration_error,
        )

    def on_enumeration_error(self, failure):
        """枚举失败 → 中止整轮（决策 6）：fetch_state 保持 FETCH_FAILED。"""
        logger.error("[nowcoder-spider] 公司枚举请求失败（%s），中止整轮",
                     failure.type.__name__ if failure.type else failure)
        self.fetch_state = FetchState.FETCH_FAILED
        raise CloseSpider("company enumeration failed")

    def parse_companies(self, response, page: int):
        state, data = self.fetch_json(response)
        if state is not FetchState.OK:
            logger.error("[nowcoder-spider] 公司枚举 HTTP/解析失败"
                         "（status=%s），中止整轮", response.status)
            raise CloseSpider("company enumeration failed")

        # 200 包裹 success:false → 业务错误，同样中止（决策 5/6）
        if not isinstance(data, dict) or data.get("success") is not True:
            logger.error("[nowcoder-spider] 公司枚举业务错误（success:false），"
                         "中止整轮：%s", str(data)[:200])
            raise CloseSpider("company enumeration business error")

        payload = data.get("data") or {}
        total_page = int(payload.get("totalPage") or 1)
        for rec in payload.get("records") or []:
            company_id, name = rec.get("companyId"), (rec.get("name") or "").strip()
            if company_id is None or not name:
                continue
            self._companies.append((company_id, name))
        self.note_parse_result(response, len(self._companies))

        logger.info("[nowcoder-spider] 枚举 page=%d/%d，累计 %d 家",
                    page, total_page, len(self._companies))

        if page < total_page:
            yield Request(
                f"{COMPANY_LIST_URL}?page={page + 1}&pageSize={COMPANY_PAGE_SIZE}",
                callback=self.parse_companies,
                cb_kwargs={"page": page + 1},
                errback=self.on_enumeration_error,
            )
            return

        # 枚举完成 → 才开始逐公司拉岗位（决策 6：不产生半轮数据）
        logger.info("[nowcoder-spider] 枚举完成，共 %d 家（limit=%s），开始拉岗位",
                    len(self._companies), self.company_limit)
        yield from self._request_job_list(self._companies)

    # ── 逐公司岗位（失败隔离：单公司失败仅 warning，决策 6）───────────────────

    def _request_job_list(self, companies):
        if self.company_limit:  # 本地试跑/限流：只取前 N 家（tasks 3.4）
            companies = companies[:self.company_limit]
        seen = set()
        for company_id, name in companies:
            if company_id in seen:
                continue
            seen.add(company_id)
            yield Request(
                f"{JOB_LIST_URL}?companyId={company_id}&page=1&pageSize={JOB_PAGE_SIZE}",
                callback=self.parse_job_list,
                cb_kwargs={"company_id": company_id, "company_name": name,
                           "page": 1},
                errback=self.on_job_error,
            )

    def on_job_error(self, failure):
        """单公司请求失败（超时/连接错误/HTTP 拦截进 errback）：仅 warning。

        不触碰 fetch_state——OK 粘滞语义下保持整轮状态（决策 5：
        单公司失败不进健康度）。
        """
        logger.warning("[nowcoder-spider] 单公司岗位请求失败（%s），跳过：%s",
                       failure.type.__name__ if failure.type else failure,
                       failure.request.url)

    def parse_job_list(self, response, company_id: int, company_name: str,
                       page: int):
        # 单公司 HTTP 失败仅 warning 跳过，不触碰 fetch_state（决策 5）
        if response.status != 200:
            logger.warning("[nowcoder-spider] 公司 %s 岗位接口 HTTP %s，跳过",
                           company_name, response.status)
            return

        try:
            body = json.loads(response.text)
        except (ValueError, TypeError):
            logger.warning("[nowcoder-spider] 公司 %s 岗位接口非 JSON，跳过",
                           company_name)
            return

        if not isinstance(body, dict) or body.get("success") is not True:
            logger.warning("[nowcoder-spider] 公司 %s 岗位接口业务错误"
                           "（success:false），跳过", company_name)
            return

        payload = body.get("data") or {}
        total_page = int(payload.get("totalPage") or 1)
        records = payload.get("records") or []

        count = 0
        for raw in records:
            # 非 open 的记录跳过不入库（决策 4）
            if raw.get("status") and raw.get("status") != "open":
                continue
            job = self.normalize(raw, company_id, company_name)
            if job is None:
                continue
            yield self._to_item(job)
            count += 1
        self.note_parse_result(response, count)

        if page < total_page:
            yield Request(
                f"{JOB_LIST_URL}?companyId={company_id}&page={page + 1}"
                f"&pageSize={JOB_PAGE_SIZE}",
                callback=self.parse_job_list,
                cb_kwargs={"company_id": company_id, "company_name": company_name,
                           "page": page + 1},
                errback=self.on_job_error,
            )

    # ── 字段映射（决策 4/4b）───────────────────────────────────────────────────

    def normalize(self, raw, company_id: int, company_name: str) \
            -> NormalizedJob | None:
        job_id = raw.get("jobId")
        title = (raw.get("title") or "").strip()
        if not job_id or not title:
            logger.debug("[nowcoder-spider] 缺 jobId/title，丢弃：%s", raw)
            return None

        published_at = None
        published_ms = raw.get("publishedAt")
        if published_ms:
            try:
                published_at = datetime.fromtimestamp(published_ms / 1000,
                                                      tz=timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                logger.debug("[nowcoder-spider] bad publishedAt: %s",
                             published_ms)

        salary_text, salary_min, salary_max = parse_salary(raw)

        # description 为完整 HTML → BeautifulSoup 剥标签（同 greenhouse）
        description = BeautifulSoup(raw.get("description") or "",
                                    "html.parser").get_text(
            separator="\n", strip=True)

        return NormalizedJob(
            source=JobSource.NOWCODER,
            source_url=JOB_DETAIL_URL_TPL.format(
                company_id=company_id, job_id=job_id),
            external_id=str(job_id),
            company_name=company_name,
            job_title=title[:256],
            location=(raw.get("locations") or "").strip()[:128],
            salary=salary_text,
            salary_min=salary_min,
            salary_max=salary_max,
            # 显式赋值，不依赖 contracts 默认 EXPERIENCED（决策 4）
            recruitment_type=recruitment_type_from_title(title),
            published_at=published_at,
            update_time=datetime.now(),
            description=description,
        )
