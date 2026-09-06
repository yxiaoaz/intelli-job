"""JobItem 三新列与 JobSource 枚举扩展测试（spec tasks 1.3）。

覆盖：
- spider item → ORM（from_scrapy_item）三新列映射
- ORM → DB → ORM 往返（内存 SQLite，create_all 建表）
- JobSource 新枚举值（GREENHOUSE/LEVER/ASHBY）写入读取往返
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import JobItem
from app.models.base import Base
from app.models.constants import AcademicQualification, JobSource, RecruitmentType
from job_crawler.contracts import NormalizedJob
from job_crawler.items import JobItemScrapy


def _make_spider_item(**overrides) -> JobItemScrapy:
    from job_crawler.base_spider import BaseJobSpider

    class StubSpider(BaseJobSpider):
        name = "stub-spider"

        def normalize(self, raw):
            yield NormalizedJob(source=JobSource.GREENHOUSE,
                                source_url=raw["url"])

    job = NormalizedJob(
        source=JobSource.GREENHOUSE,
        source_url="https://stripe.com/jobs/search?gh_jid=8172508",
        company_name="Stripe",
        job_title="Software Engineer",
        location="San Francisco",
        salary="$150K – $180K",
        salary_min=150000,
        salary_max=180000,
        published_at=datetime(2026, 9, 3, 17, 32, 53, tzinfo=timezone.utc),
        update_time=datetime(2026, 9, 4, 18, 12, 20),
    )
    item = StubSpider()._to_item(job)
    for k, v in overrides.items():
        item[k] = v
    return item


# ── spider item → ORM 映射 ────────────────────────────────────────────────

class TestFromScrapyItemMapping:
    def test_new_columns_mapped(self):
        orm = JobItem.from_scrapy_item(_make_spider_item())
        assert orm.published_at == datetime(2026, 9, 3, 17, 32, 53,
                                            tzinfo=timezone.utc)
        assert orm.salary_min == 150000
        assert orm.salary_max == 180000

    def test_missing_new_columns_default_none(self):
        """旧源（未填三新列）不炸，默认 None。"""
        item = _make_spider_item(published_at=None, salary_min=None,
                                 salary_max=None)
        orm = JobItem.from_scrapy_item(item)
        assert orm.published_at is None
        assert orm.salary_min is None
        assert orm.salary_max is None


# ── 列定义 ────────────────────────────────────────────────────────────────

class TestColumnDefinitions:
    def test_column_types_and_nullable(self):
        table = JobItem.__table__
        published_at = table.columns["published_at"]
        assert published_at.nullable is True
        assert published_at.type.timezone is True  # TIMESTAMPTZ 语义
        assert table.columns["salary_min"].nullable is True
        assert table.columns["salary_max"].nullable is True


# ── ORM → DB → ORM 往返（含新枚举值） ──────────────────────────────────────

class TestRoundTrip:
    @pytest.fixture()
    def session(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
        engine.dispose()

    def test_new_columns_round_trip(self, session):
        orm = JobItem.from_scrapy_item(_make_spider_item())
        session.add(orm)
        session.commit()

        row = session.scalar(
            select(JobItem).where(JobItem.url == orm.url))
        assert row is not None
        assert row.salary_min == 150000
        assert row.salary_max == 180000
        # SQLite 会丢弃 tzinfo（PG TIMESTAMPTZ 保留），补回后比对
        assert row.published_at.replace(tzinfo=timezone.utc) == \
            datetime(2026, 9, 3, 17, 32, 53, tzinfo=timezone.utc)

    @pytest.mark.parametrize("source", [JobSource.GREENHOUSE, JobSource.LEVER,
                                        JobSource.ASHBY])
    def test_new_enum_values_round_trip(self, session, source):
        """三个 ATS 枚举值可写入读出（SQLite 非原生 enum，走 VARCHAR 校验）。"""
        session.add(JobItem(
            id=uuid.uuid4(), source=source,
            url=f"https://example.test/{source.name.lower()}/1",
            fingerprint=f"fp-{source.name}", job_title="T",
        ))
        session.commit()
        row = session.scalar(
            select(JobItem).where(JobItem.source == source))
        assert row.source is source

    def test_enum_values_registered(self):
        assert JobSource.GREENHOUSE.value == "Greenhouse"
        assert JobSource.LEVER.value == "Lever"
        assert JobSource.ASHBY.value == "Ashby"
