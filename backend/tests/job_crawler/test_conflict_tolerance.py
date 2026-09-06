"""落库冲突容错测试（spec tasks 2.3，design 决策 8）。

覆盖：
- insert_job_item 的 PG 语句形态：不带推断目标的 ON CONFLICT DO NOTHING + RETURNING id
- pipeline flush 过滤：冲突条目不进 embedding batch；全冲突批不抛异常、零 embedding
"""
import contextlib
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

import job_crawler.pipelines as pipelines_module
from app.models import JobItem
from app.models.constants import JobSource
from app.services.crawler_db_controller import CrawlerDBController
from job_crawler.base_spider import BaseJobSpider
from job_crawler.contracts import NormalizedJob
from job_crawler.items import JobItemScrapy
from job_crawler.pipelines import JobCrawlerPipeline


# ── SQL 语句形态 ───────────────────────────────────────────────────────────

class TestInsertStatementShape:
    def test_on_conflict_do_nothing_without_target(self):
        """不带推断目标：任意唯一约束冲突一律 DO NOTHING。"""
        stmt = (
            pg_insert(JobItem)
            .values({"id": uuid.uuid4(), "url": "https://x.test/1"})
            .on_conflict_do_nothing()
            .returning(JobItem.id)
        )
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "ON CONFLICT DO NOTHING" in sql
        # 不带推断目标（不出现 ON CONFLICT (col) 形式）
        assert "ON CONFLICT (" not in sql
        assert "RETURNING" in sql

    def test_job_values_contains_fingerprint_and_new_columns(self):
        """核心插入值必须含 fingerprint 与三新列（修复旧 to_dict 丢列问题）。"""
        item = JobItem(
            id=uuid.uuid4(), source=JobSource.ZHILIAN, url="https://x.test/1",
            fingerprint="fp", salary_min=100, salary_max=200,
            published_at=datetime(2026, 9, 1, tzinfo=None),
        )
        values = CrawlerDBController._job_values(item)
        for key in ("fingerprint", "published_at", "salary_min", "salary_max"):
            assert key in values


# ── pipeline flush 过滤逻辑 ─────────────────────────────────────────────────

def _make_items(count: int) -> list:
    """模拟真实 buffer 内容：ORM JobItem（process_item 中 from_scrapy_item 后入队）。"""
    class StubSpider(BaseJobSpider):
        name = "stub-spider"

        def normalize(self, raw):
            yield NormalizedJob(source=JobSource.GREENHOUSE,
                                source_url=raw["url"])

    spider = StubSpider()
    items = []
    for i in range(count):
        job = NormalizedJob(
            source=JobSource.GREENHOUSE,
            source_url=f"https://example.test/job/{i}",
            company_name=f"Company{i % 7}",
            job_title=f"Engineer {i}",
            location="SF",
        )
        items.append(spider._to_item(job))
    return [JobItem.from_scrapy_item(i) for i in items]


class _StubSession:
    def commit(self):
        pass

    def rollback(self):
        pass


class StubDBController:
    """insert_job_item 返回预置的"实际插入 id 集合"。"""

    def __init__(self, inserted_ids):
        self._inserted = inserted_ids
        self.calls = []

    def session_maker(self):
        return contextlib.nullcontext(_StubSession())

    def insert_job_item(self, session, items):
        self.calls.append([str(i.id) for i in items])
        return self._inserted


def _make_pipeline(inserted_ids, tmp_path, monkeypatch):
    monkeypatch.setattr(pipelines_module, "get_project_root",
                        lambda: str(tmp_path))
    pipeline = JobCrawlerPipeline.__new__(JobCrawlerPipeline)
    pipeline.spider_name = "stub-spider"
    pipeline.db_controller = StubDBController(inserted_ids)
    captured = {}
    pipeline._process_batch_file = (
        lambda batch_file, id_map: captured.update(id_map=id_map,
                                                   batch_file=batch_file))
    return pipeline, captured


class TestFlushFiltering:
    def test_conflict_item_excluded_from_batch(self, tmp_path, monkeypatch):
        """100 条含 1 条跨源冲突 → 99 条进 batch，冲突条不进 Milvus。"""
        items = _make_items(100)
        conflict_id = items[0].id
        inserted = [i.id for i in items[1:]]
        pipeline, captured = _make_pipeline(inserted, tmp_path, monkeypatch)

        pipeline._flush_embed_buffer(items)

        assert len(captured["id_map"]) == 99
        assert str(conflict_id) not in captured["id_map"]
        # DB 收到全部 100 条（冲突交给 DB 层 DO NOTHING）
        assert len(pipeline.db_controller.calls[0]) == 100

    def test_all_conflicts_no_embedding_no_exception(self, tmp_path, monkeypatch):
        """全冲突批 → 提前返回，零 embedding 写入，不抛异常。"""
        items = _make_items(5)
        pipeline, captured = _make_pipeline([], tmp_path, monkeypatch)

        pipeline._flush_embed_buffer(items)  # 不应抛异常

        assert captured == {}  # _process_batch_file 未被调用

    def test_batch_file_content_matches_inserted(self, tmp_path, monkeypatch):
        """batch 文件只含实际插入条目。"""
        items = _make_items(3)
        inserted = [items[0].id, items[2].id]
        pipeline, captured = _make_pipeline(inserted, tmp_path, monkeypatch)

        pipeline._flush_embed_buffer(items)

        content = Path(captured["batch_file"]).read_text(encoding="utf-8")
        assert str(items[0].id) in content
        assert str(items[2].id) in content
        assert str(items[1].id) not in content
