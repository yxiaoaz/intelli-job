# -*- coding: utf-8 -*-
"""BaseJobSpider：采集层统一基类。

四态判别、指纹计算、item 转换全部收敛在此，子类只写"取数 + normalize"。
参见 openspec/changes/job-source-adapter-refactor/design.md（决策 1/2/3）。

用法（JSON API 型源，如 Greenhouse/Lever）::

    class XxxSpider(BaseJobSpider):
        def start_requests(self):
            yield scrapy.Request(api_url, callback=self.parse_board,
                                 errback=self.on_fetch_error)

        def parse_board(self, response):
            state, data = self.fetch_json(response)
            if state is not FetchState.OK:
                return
            count = 0
            for raw in data:
                yield self._to_item(self.normalize(raw))
                count += 1
            self.fetch_state = self.classify_response(response, parsed_count=count)

用法（HTML 型源）::

    def parse(self, response):
        ...
        self.fetch_state = self.classify_response(response, parsed_count=len(jobs))
"""
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Union

from scrapy import Spider

from app.models.constants import JobSource
from job_crawler.contracts import FetchState, NormalizedJob, compute_fingerprint
from job_crawler.items import JobItemScrapy

logger = logging.getLogger(__name__)


def load_verified_boards(ats_type: str) -> list[dict]:
    """读注册表 status=VERIFIED 的 board（ats-job-source-integration）。

    返回 [{company_name, board_slug}]；注册表未建/异常时返回空列表。
    """
    try:
        from sqlalchemy import select

        from app.models import JobAtsRegistry
        from app.services.crawler_db_controller import CrawlerDBController

        controller = CrawlerDBController()
        with controller.session_maker() as session:
            rows = session.scalars(select(JobAtsRegistry).where(
                JobAtsRegistry.status == "VERIFIED",
                JobAtsRegistry.ats_type == ats_type,
            )).all()
            return [{"company_name": r.company_name,
                     "board_slug": r.board_slug} for r in rows]
    except Exception as e:
        logger.error("load_verified_boards failed for %s: %s", ats_type, e)
        return []


class BaseJobSpider(Spider, ABC):
    """所有岗位源（爬虫型与 JSON API 型）的统一基类。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 默认失败：spider 启动后从未成功解析时，健康度按 FETCH_FAILED 记
        self.fetch_state: FetchState = FetchState.FETCH_FAILED
        # 本轮 404 的 board 标识（健康度联动注册表标 DEAD 时定位脏数据）
        self.no_board_slugs: set = set()

    def mark_no_board(self, slug: str) -> None:
        """子类在确认某 board 404 时调用（如 spider 参数化的 board slug）。"""
        self.no_board_slugs.add(slug)

    # ── 四态判别 ───────────────────────────────────────────────────────────

    def fetch_json(self, response) -> tuple[FetchState, Union[dict, list, None]]:
        """JSON API 源的统一四态判别。

        404→NO_BOARD；200→解析 JSON（data 可能为 dict 或裸数组，
        也可能 200 + 空容器——是否 EMPTY 由调用方结合 parsed_count 判定）；
        5xx/403/429/非 JSON→FETCH_FAILED。超时/连接错误不进入回调，
        由 on_fetch_error 兜底标记 FETCH_FAILED。
        """
        status = getattr(response, "status", None)
        if status == 404:
            self.fetch_state = FetchState.NO_BOARD
            return FetchState.NO_BOARD, None
        if status != 200:
            self.fetch_state = FetchState.FETCH_FAILED
            return FetchState.FETCH_FAILED, None

        try:
            data = json.loads(response.text)
        except (ValueError, TypeError):
            logger.warning("[%s] Non-JSON response from %s", self.name,
                           getattr(response, "url", "?"))
            self.fetch_state = FetchState.FETCH_FAILED
            return FetchState.FETCH_FAILED, None

        # 200 且 JSON 合法：内容层面（空数组/空对象）不算失败，
        # EMPTY 与否交给 classify_response 按"解析产出 0 条"判定
        return FetchState.OK, data

    def classify_response(self, response, parsed_count: Union[int, None] = None) -> FetchState:
        """HTML 源的响应级四态钩子（JSON 源也可复用）。

        默认实现：HTTP 404→NO_BOARD、非 200→FETCH_FAILED、
        解析产出 0 条→EMPTY（主判据）、其余→OK。
        页面文本标记（"无数据/暂无"）仅可作子类内的辅助信号，
        不得作为独立判据——列表页"暂无更多职位"类分页文案会误触发。
        """
        status = getattr(response, "status", None)
        if status == 404:
            return FetchState.NO_BOARD
        if status != 200:
            return FetchState.FETCH_FAILED
        if parsed_count == 0:
            return FetchState.EMPTY
        return FetchState.OK

    def note_parse_result(self, response, parsed_count: int) -> None:
        """解析后更新 fetch_state：OK 粘滞——一旦有产出，

        后续个别空页/404 不降级整体状态（多请求源的聚合语义）。
        """
        state = self.classify_response(response, parsed_count=parsed_count)
        if state is FetchState.OK or self.fetch_state is not FetchState.OK:
            self.fetch_state = state

    def on_fetch_error(self, failure) -> None:
        """Request errback 兜底。

        - 404（被 HttpErrorMiddleware 拦截进 errback）：记入 no_board_slugs
          并标记 NO_BOARD（不降级已 OK 的状态）；
        - 超时/连接失败/DNS 等：标记 FETCH_FAILED（同样不降级 OK）。
        """
        logger.error("[%s] Fetch failed: %s (%s)", self.name,
                     getattr(failure.request, "url", "?"), failure.value)
        response = getattr(failure.value, "response", None)
        if response is not None and getattr(response, "status", None) == 404:
            slug = (getattr(failure.request, "cb_kwargs", None) or {}).get("slug")
            if slug:
                self.mark_no_board(slug)
            if self.fetch_state is not FetchState.OK:
                self.fetch_state = FetchState.NO_BOARD
            return
        if self.fetch_state is not FetchState.OK:
            self.fetch_state = FetchState.FETCH_FAILED

    # ── 归一化与 item 转换 ─────────────────────────────────────────────────

    def emit_items(self, response):
        """HTML 回调统一出口：normalize → _to_item → 更新 fetch_state。"""
        jobs = list(self.normalize(response))
        self.note_parse_result(response, len(jobs))
        yield from (self._to_item(j) for j in jobs)

    @abstractmethod
    def normalize(self, raw) -> Iterable[NormalizedJob]:
        """每源唯一必写方法：原始记录（HTML 源为 response，API 源为 dict）
        → 归一化结果（可产出多条或零条）。"""

    def _to_item(self, job: NormalizedJob) -> JobItemScrapy:
        """统一转换：id 仍按 uuid3(url)（Redis URL 去重语义不变），
        指纹改为跨源算法（company|title|location）。

        各字段按 DB 列宽防御性截断（如 Greenhouse 组合式 location
        超 String(128)），避免整批入库失败。
        """
        return JobItemScrapy(
            id=uuid.uuid3(uuid.NAMESPACE_URL, job.source_url),
            source=job.source,
            url=job.source_url,
            fingerprint=compute_fingerprint(job.company_name, job.job_title,
                                            job.location),
            job_title=job.job_title[:256],
            location=job.location[:128],
            recruitment_type=job.recruitment_type,
            min_academic_qualification=job.min_academic_qualification,
            salary=(job.salary or "")[:128] or None,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            published_at=job.published_at,
            update_time=job.update_time or datetime.now(),
            description=job.description,
            company_name=job.company_name[:256],
        )
