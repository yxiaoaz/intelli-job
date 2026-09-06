"""backfill_fingerprint 回填脚本核心逻辑测试（spec tasks 2.2）。

用内存 SQLite 模拟 job_items 表、stub VectorDBService，
验证 dry-run/apply 的分组、保留规则与幂等性，不触真实环境。
"""
import importlib.util
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import JobItem
from app.models.base import Base
from app.models.constants import JobSource
from job_crawler.contracts import compute_fingerprint

_SCRIPT = (Path(__file__).resolve().parents[2] / "scripts"
           / "backfill_fingerprint.py")
_spec = importlib.util.spec_from_file_location("backfill_fingerprint", _SCRIPT)
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)


def _job(url: str, company: str, title: str, location: str,
         update_time=None, fp: str | None = None) -> JobItem:
    return JobItem(
        id=uuid.uuid4(), source=JobSource.ZHILIAN, url=url,
        fingerprint=fp or str(uuid.uuid4()),
        job_title=title, company_name=company, location=location,
        update_time=update_time,
    )


@pytest.fixture()
def env(monkeypatch):
    """内存库 + 两个跨 URL 冲突岗 + 一个无关岗。"""
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    t_old = datetime(2026, 1, 1)
    t_new = datetime(2026, 6, 1)
    newer = _job("https://a.test/1", "Stripe, Inc.", "Software Engineer",
                 "SF", t_new)
    older = _job("https://b.test/2", "stripe inc", "software   engineer!",
                 "SF", t_old)  # 归一化后与 newer 冲突
    other = _job("https://c.test/3", "Linear", "Engineer", "Remote",
                 t_new)
    with Session(engine) as s:
        s.add_all([newer, older, other])
        s.commit()
        # session 关闭前取主键，避免 DetachedInstanceError
        ids = {"newer": newer.id, "older": older.id, "other": other.id}

    maker = sessionmaker(bind=engine)

    class StubController:
        session_maker = maker

    class StubVectorDB:
        deleted: list = []

        def delete_embeddings_by_ids(self, ids):
            StubVectorDB.deleted.extend(ids)

    monkeypatch.setattr(bf, "CrawlerDBController", StubController)
    monkeypatch.setattr("app.services.vector_db_service.VectorDBService",
                        StubVectorDB)
    yield {"engine": engine, "ids": ids, "vector": StubVectorDB}
    engine.dispose()


class TestAnalyze:
    def test_conflict_group_detection(self, env):
        rows, groups = bf.analyze()
        assert len(rows) == 3
        assert len(groups) == 1
        g = groups[0]
        assert g["keeper"].id == env["ids"]["newer"]  # update_time 最大者保留
        assert [r.id for r in g["losers"]] == [env["ids"]["older"]]


class TestApply:
    def test_apply_deletes_losers_updates_fingerprints(self, env):
        rows, groups = bf.analyze()
        summary = bf.apply(rows, groups)

        assert summary["deleted"] == 1
        assert summary["kept"] == 2
        # Milvus 删除先于 SQL（stub 记录被删 id）
        assert env["vector"].deleted == [env["ids"]["older"]]

        with Session(env["engine"]) as s:
            all_rows = s.scalars(select(JobItem)).all()
            assert len(all_rows) == 2
            by_url = {r.url: r for r in all_rows}
            # 保留行指纹为新算法
            kept = by_url["https://a.test/1"]
            assert kept.fingerprint == compute_fingerprint(
                "Stripe, Inc.", "Software Engineer", "SF")
            # 无关行指纹也切换到新算法
            assert by_url["https://c.test/3"].fingerprint == compute_fingerprint(
                "Linear", "Engineer", "Remote")
            # 冲突败者已删除（by_url 中不存在该键）
            assert "https://b.test/2" not in by_url

    def test_idempotent_second_run(self, env):
        rows, groups = bf.analyze()
        bf.apply(rows, groups)

        rows2, groups2 = bf.analyze()
        assert groups2 == []
        summary2 = bf.apply(rows2, groups2)
        assert summary2["deleted"] == 0
        assert summary2["fingerprints_updated"] == 0


class TestDryRun:
    def test_report_written_no_db_writes(self, env, tmp_path, monkeypatch):
        monkeypatch.setattr(bf, "BACKEND_DIR", tmp_path)
        rows, groups = bf.analyze()
        report = bf.dry_run(rows, groups)
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "https://b.test/2" in content
        # dry-run 不写库
        with Session(env["engine"]) as s:
            assert len(s.scalars(select(JobItem)).all()) == 3
