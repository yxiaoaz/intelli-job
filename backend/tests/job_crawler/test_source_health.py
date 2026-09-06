"""源健康度测试（spec tasks 3.1 / 3.2，design 决策 5）。

覆盖：
- 连续 FETCH_FAILED 3 次 → DEGRADED、10 次 → DISABLED
- 复检 OK → 复位 ACTIVE（DISABLED 自愈）
- 连续 EMPTY 10 次不触发 DISABLED（不计 ok/fail）
- NO_BOARD 独立计数；注册表未建时联动仅记日志不抛异常
- 调度层 filter_disabled_sources：DISABLED 跳过 / 7 天放行 / DEGRADED 告警放行
"""
import importlib.util
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import JobAtsRegistry, JobSourceHealth
from app.models.constants import JobSource
from job_crawler.contracts import FetchState
from job_crawler.pipelines import JobSourceHealthPipeline


@pytest.fixture()
def db():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    JobSourceHealth.__table__.create(engine)
    yield engine
    engine.dispose()


class FakeSpider:
    name = "fake-spider"

    def __init__(self, source, state, slugs=None):
        self.job_source = source
        self.fetch_state = state
        self.no_board_slugs = slugs or set()


def _make_pipeline(engine) -> JobSourceHealthPipeline:
    pipeline = JobSourceHealthPipeline.__new__(JobSourceHealthPipeline)
    pipeline.spider_name = "fake-spider"
    pipeline._ok_count = 0
    maker = sessionmaker(bind=engine)

    class StubController:
        session_maker = maker

    pipeline.db_controller = StubController()
    return pipeline


def _get_row(engine, source):
    with Session(engine) as s:
        return s.get(JobSourceHealth, source)


class TestHealthStateTransitions:
    def test_three_failures_degrade_then_ok_resets(self, db):
        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.ZHILIAN, FetchState.FETCH_FAILED)
        for _ in range(3):
            pipeline.close_spider(spider)
        assert _get_row(db, JobSource.ZHILIAN).status == "DEGRADED"

        pipeline._ok_count = 5
        spider.fetch_state = FetchState.OK
        pipeline.close_spider(spider)
        row = _get_row(db, JobSource.ZHILIAN)
        assert row.status == "ACTIVE"
        assert row.consecutive_fail == 0
        assert row.ok_count == 5
        assert row.last_ok_at is not None

    def test_ten_failures_disable_then_recheck_ok_heals(self, db):
        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.SHIXISENG, FetchState.FETCH_FAILED)
        for _ in range(10):
            pipeline.close_spider(spider)
        assert _get_row(db, JobSource.SHIXISENG).status == "DISABLED"

        # 复检仍失败：保持 DISABLED
        pipeline.close_spider(spider)
        assert _get_row(db, JobSource.SHIXISENG).status == "DISABLED"

        # 复检 OK：复位（自愈）
        pipeline._ok_count = 3
        spider.fetch_state = FetchState.OK
        pipeline.close_spider(spider)
        assert _get_row(db, JobSource.SHIXISENG).status == "ACTIVE"

    def test_empty_never_disables(self, db):
        """连续 EMPTY 10 次：不计 ok/fail，不触发 DISABLED。"""
        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.GREENHOUSE, FetchState.EMPTY)
        for _ in range(10):
            pipeline.close_spider(spider)
        row = _get_row(db, JobSource.GREENHOUSE)
        assert row.status == "ACTIVE"
        assert row.ok_count == 0
        assert row.fail_count == 0
        assert row.consecutive_fail == 0
        assert row.last_run_at is not None

    def test_no_board_counts_independently_registry_absent_ok(self, db):
        """NO_BOARD 不计 fail；注册表未建时 DEAD 联动仅记日志不抛异常。"""
        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.LEVER, FetchState.NO_BOARD,
                            slugs={"tiktok"})
        for _ in range(3):
            pipeline.close_spider(spider)  # 注册表未建：不抛异常
        row = _get_row(db, JobSource.LEVER)
        assert row.consecutive_no_board == 3
        assert row.fail_count == 0
        assert row.consecutive_fail == 0

    def test_mixed_ok_with_404_slug_marks_registry_dead(self, db):
        """多 board 源整体 OK 但含 404 slug：连续 3 轮 → 注册表标 DEAD。"""
        JobAtsRegistry.__table__.create(db)
        with Session(db) as s:
            reg = JobAtsRegistry(company_name="Ghost", ats_type="lever",
                                 board_slug="ghost", status="VERIFIED")
            s.add(reg)
            s.commit()
            reg_id = reg.id

        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.LEVER, FetchState.OK, slugs={"ghost"})
        pipeline._ok_count = 10
        for _ in range(3):
            pipeline.close_spider(spider)

        with Session(db) as s:
            assert s.get(JobAtsRegistry, reg_id).status == "DEAD"
            health = s.get(JobSourceHealth, JobSource.LEVER)
            # 源本身存活：不计 fail，状态保持 ACTIVE
            assert health.status == "ACTIVE"
            assert health.fail_count == 0
            assert health.ok_count == 30
        JobAtsRegistry.__table__.drop(db)

    def test_ok_resets_no_board_counter(self, db):
        pipeline = _make_pipeline(db)
        spider = FakeSpider(JobSource.LEVER, FetchState.OK, slugs={"x"})
        pipeline.close_spider(spider)
        pipeline.close_spider(spider)
        spider.no_board_slugs = set()  # 第 3 轮 404 恢复
        pipeline.close_spider(spider)
        assert _get_row(db, JobSource.LEVER).consecutive_no_board == 0

    def test_missing_job_source_skipped(self, db):
        class NoSourceSpider:
            name = "no-source"
            fetch_state = FetchState.OK

        pipeline = _make_pipeline(db)
        pipeline.close_spider(NoSourceSpider())  # 不抛异常
        with Session(db) as s:
            assert s.scalars(select(JobSourceHealth)).all() == []


# ── 调度层消费（run_crawler.filter_disabled_sources） ──────────────────────

_rc_spec = importlib.util.spec_from_file_location(
    "run_crawler", Path(__file__).resolve().parents[2] / "run_crawler.py")
run_crawler = importlib.util.module_from_spec(_rc_spec)
_rc_spec.loader.exec_module(run_crawler)


class _StubSession:
    def commit(self):
        pass


@pytest.fixture()
def schedule_env(db, monkeypatch):
    maker = sessionmaker(bind=db)

    class StubController:
        session_maker = maker

    from app.services import crawler_db_controller as cdc_module
    monkeypatch.setattr(cdc_module, "CrawlerDBController", StubController)
    return db


def _seed_health(engine, source, status, last_run_at):
    with Session(engine) as s:
        s.add(JobSourceHealth(source=source, status=status,
                              last_run_at=last_run_at))
        s.commit()


class _StubSpiderCls:
    def __init__(self, name, source):
        self.name = name
        self.job_source = source


class TestFilterDisabledSources:
    def test_no_record_allowed(self, schedule_env):
        cls = _StubSpiderCls("zhilian", JobSource.ZHILIAN)
        assert run_crawler.filter_disabled_sources([cls]) == [cls]

    def test_degraded_allowed_with_warning(self, schedule_env, capsys):
        _seed_health(schedule_env, JobSource.ZHILIAN, "DEGRADED",
                     datetime.utcnow())
        cls = _StubSpiderCls("zhilian", JobSource.ZHILIAN)
        assert run_crawler.filter_disabled_sources([cls]) == [cls]
        assert "DEGRADED" in capsys.readouterr().out

    def test_disabled_within_window_skipped(self, schedule_env):
        _seed_health(schedule_env, JobSource.SHIXISENG, "DISABLED",
                     datetime.utcnow() - timedelta(days=1))
        cls = _StubSpiderCls("shixiseng", JobSource.SHIXISENG)
        assert run_crawler.filter_disabled_sources([cls]) == []

    def test_disabled_after_7d_recheck_allowed(self, schedule_env):
        _seed_health(schedule_env, JobSource.SHIXISENG, "DISABLED",
                     datetime.utcnow() - timedelta(days=8))
        cls = _StubSpiderCls("shixiseng", JobSource.SHIXISENG)
        assert run_crawler.filter_disabled_sources([cls]) == [cls]

    def test_missing_job_source_allowed(self, schedule_env):
        class LegacySpider:
            name = "legacy"

        assert run_crawler.filter_disabled_sources([LegacySpider()]) != []
