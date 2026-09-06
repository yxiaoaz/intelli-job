"""BaseJobSpider 单元测试（离线，fixtures 真实样本驱动）。

覆盖（spec tasks 1.2）：
- fetch_json 四态判别：404/200+JSON/裸数组/空数组/非 200/非 JSON
- classify_response 默认实现：404/非 200/parsed_count=0/parsed_count>0
- on_fetch_error 兜底 FETCH_FAILED
- _to_item：统一指纹计算、id=uuid3(url)、三新列透传
- normalize 抽象强制
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.constants import JobSource, RecruitmentType
from job_crawler.base_spider import BaseJobSpider
from job_crawler.contracts import FetchState, NormalizedJob

FIXTURES = Path(__file__).resolve().parents[2] / "job_crawler" / "fixtures"


def load_fixture(*parts: str) -> str:
    return (FIXTURES.joinpath(*parts)).read_text(encoding="utf-8")


class FakeResponse:
    """轻量响应替身：fetch_json/classify_response 只依赖 status/text/url。"""

    def __init__(self, status: int = 200, text: str = "",
                 url: str = "https://example.test/api"):
        self.status = status
        self.text = text
        self.url = url


class StubSpider(BaseJobSpider):
    """最小具体子类：normalize 直通单条。"""

    name = "stub-spider"

    def normalize(self, raw):
        yield NormalizedJob(
            source=JobSource.GREENHOUSE,
            source_url=raw["url"],
            external_id=str(raw.get("external_id", "")),
            company_name=raw["company"],
            job_title=raw["title"],
            location=raw["location"],
            published_at=raw.get("published_at"),
        )


# ── fetch_json 四态判别 ────────────────────────────────────────────────────

class TestFetchJson:
    def setup_method(self):
        self.spider = StubSpider()

    def test_200_object_json_is_ok(self):
        """greenhouse 样本：200 + {"jobs": [...]} → OK（dict）。"""
        resp = FakeResponse(text=load_fixture("greenhouse", "stripe-jobs.json"))
        state, data = self.spider.fetch_json(resp)
        assert state is FetchState.OK
        assert isinstance(data, dict) and len(data["jobs"]) >= 1

    def test_200_bare_list_is_ok_not_empty(self):
        """lever 样本：200 + 裸数组 → OK（list），禁止 .get('jobs') 误判。"""
        resp = FakeResponse(text=load_fixture("lever", "matchgroup-jobs.json"))
        state, data = self.spider.fetch_json(resp)
        assert state is FetchState.OK
        assert isinstance(data, list) and len(data) >= 1

    def test_200_empty_array_ok_at_fetch_level(self):
        """smartrecruiters 样本：200 + [] → fetch 层 OK，EMPTY 由 parsed_count 判。"""
        resp = FakeResponse(text=load_fixture("smartrecruiters", "wipro-postings.json"))
        state, data = self.spider.fetch_json(resp)
        assert state is FetchState.OK
        assert data == []

    def test_404_is_no_board(self):
        resp = FakeResponse(status=404, text="not found")
        state, data = self.spider.fetch_json(resp)
        assert state is FetchState.NO_BOARD
        assert data is None
        assert self.spider.fetch_state is FetchState.NO_BOARD

    @pytest.mark.parametrize("status", [403, 429, 500, 503])
    def test_http_errors_are_fetch_failed(self, status):
        resp = FakeResponse(status=status, text="blocked")
        state, _ = self.spider.fetch_json(resp)
        assert state is FetchState.FETCH_FAILED
        assert self.spider.fetch_state is FetchState.FETCH_FAILED

    def test_non_json_body_is_fetch_failed(self):
        resp = FakeResponse(status=200, text="<html>blocked by waf</html>")
        state, data = self.spider.fetch_json(resp)
        assert state is FetchState.FETCH_FAILED
        assert data is None

    def test_default_state_is_fetch_failed(self):
        """spider 启动后从未成功解析 → 默认 FETCH_FAILED。"""
        assert StubSpider().fetch_state is FetchState.FETCH_FAILED


# ── classify_response 默认实现 ─────────────────────────────────────────────

class TestClassifyResponse:
    def setup_method(self):
        self.spider = StubSpider()

    def test_404_no_board(self):
        assert self.spider.classify_response(
            FakeResponse(status=404)) is FetchState.NO_BOARD

    @pytest.mark.parametrize("status", [403, 500, 502])
    def test_non_200_fetch_failed(self, status):
        assert self.spider.classify_response(
            FakeResponse(status=status)) is FetchState.FETCH_FAILED

    def test_parsed_zero_is_empty(self):
        """主判据：解析产出 0 条 → EMPTY（而非 fetch 失败或 no_board）。"""
        assert self.spider.classify_response(
            FakeResponse(status=200), parsed_count=0) is FetchState.EMPTY

    def test_parsed_positive_is_ok(self):
        assert self.spider.classify_response(
            FakeResponse(status=200), parsed_count=3) is FetchState.OK


# ── errback 兜底 ───────────────────────────────────────────────────────────

class TestOnError:
    def test_on_fetch_error_sets_fetch_failed(self):
        class FakeFailure:
            class request:
                url = "https://example.test/api"
                cb_kwargs = {}

            value = TimeoutError("timed out")

        spider = StubSpider()
        spider.on_fetch_error(FakeFailure())
        assert spider.fetch_state is FetchState.FETCH_FAILED

    def test_on_fetch_error_404_marks_no_board_slug(self):
        """404 被 HttpErrorMiddleware 拦截进 errback：记 slug、标 NO_BOARD。"""
        class FakeFailure:
            class request:
                url = "https://example.test/boards/ghost/jobs"
                cb_kwargs = {"slug": "ghost", "company_name": "Ghost"}

            class value:
                class response:
                    status = 404

        spider = StubSpider()
        spider.on_fetch_error(FakeFailure())
        assert spider.no_board_slugs == {"ghost"}
        assert spider.fetch_state is FetchState.NO_BOARD

    def test_on_fetch_error_404_does_not_downgrade_ok(self):
        """多 board 源整体 OK 时，个别 404 不降级状态，但 slug 仍被记录。"""
        class FakeFailure:
            class request:
                url = "https://example.test/boards/ghost/jobs"
                cb_kwargs = {"slug": "ghost"}

            class value:
                class response:
                    status = 404

        spider = StubSpider()
        spider.fetch_state = FetchState.OK
        spider.on_fetch_error(FakeFailure())
        assert spider.fetch_state is FetchState.OK
        assert spider.no_board_slugs == {"ghost"}


# ── _to_item 统一转换 ──────────────────────────────────────────────────────

class TestToItem:
    def _job(self) -> NormalizedJob:
        return NormalizedJob(
            source=JobSource.GREENHOUSE,
            source_url="https://stripe.com/jobs/search?gh_jid=8172508",
            external_id="8172508",
            company_name="Stripe, Inc.",
            job_title="Software  Engineer!",
            location="San Francisco",
            salary="$150K – $180K",
            salary_min=150000,
            salary_max=180000,
            recruitment_type=RecruitmentType.INTERN,
            published_at=datetime(2026, 9, 3, 17, 32, 53, tzinfo=timezone.utc),
            update_time=datetime(2026, 9, 4, 18, 12, 20),
        )

    def test_fingerprint_computed_cross_source(self):
        """指纹=sha1(company|title|location)，与 URL 无关。"""
        from job_crawler.contracts import compute_fingerprint

        item = StubSpider()._to_item(self._job())
        assert item["fingerprint"] == compute_fingerprint(
            "Stripe, Inc.", "Software  Engineer!", "San Francisco")
        assert item["fingerprint"] != compute_fingerprint(
            "Stripe, Inc.", "Software  Engineer!", "Dublin")

    def test_id_is_uuid3_of_url(self):
        """id 保持 uuid3(url)——Redis URL 去重语义不变。"""
        item = StubSpider()._to_item(self._job())
        assert item["id"] == uuid.uuid3(uuid.NAMESPACE_URL, self._job().source_url)

    def test_new_columns_passthrough(self):
        item = StubSpider()._to_item(self._job())
        assert item["published_at"] == datetime(2026, 9, 3, 17, 32, 53,
                                                tzinfo=timezone.utc)
        assert item["salary_min"] == 150000
        assert item["salary_max"] == 180000

    def test_update_time_defaults_to_now(self):
        job = self._job()
        job.update_time = None
        item = StubSpider()._to_item(job)
        assert isinstance(item["update_time"], datetime)


# ── 抽象强制 ───────────────────────────────────────────────────────────────

class TestAbstract:
    def test_missing_normalize_rejected(self):
        class NoNormalize(BaseJobSpider):
            name = "no-normalize"

        with pytest.raises(TypeError):
            NoNormalize()
