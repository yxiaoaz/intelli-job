"""ATS 探测脚本与种子灌库测试（ats-job-source-integration tasks 1.1/1.2）。

四态路径：404→UNVERIFIED 保持、200+0→VERIFIED（EMPTY 也是 board 存在）、
200+n→VERIFIED、超时→FETCH_FAILED。全部离线（FakeClient 注入）。
"""
import importlib.util
import json
from datetime import datetime, timedelta
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import JobAtsRegistry
from app.models.base import Base

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    path = (_SCRIPTS / name).with_suffix(".py")
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_file_location(name, str(path), loader=loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load("probe_ats_boards")
seed = _load("load_ats_seed")


class FakeResponse:
    def __init__(self, status, body=""):
        self.status_code = status
        self.text = body


class FakeClient:
    """按 (ats_type, slug) 返回预置响应；未命中默认 404。"""

    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.requested: list = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        for (ats_type, slug), resp in self.responses.items():
            template = probe.ENDPOINTS[ats_type]
            if url.startswith(template.format(slug=slug)):
                return resp
        return FakeResponse(404)


# ── 四态判别 ───────────────────────────────────────────────────────────────

class TestClassifyProbeResponse:
    def test_200_with_jobs_is_ok(self):
        body = json.dumps({"jobs": [{"id": 1}, {"id": 2}]})
        state, n = probe.classify_probe_response(200, body)
        assert state.name == "OK" and n == 2

    def test_200_bare_array_is_ok(self):
        state, n = probe.classify_probe_response(200, json.dumps([{"id": 1}]))
        assert state.name == "OK" and n == 1

    def test_200_empty_is_empty_not_404(self):
        """SmartRecruiters 式 200+totalFound=0：board 存在但零岗位。"""
        state, n = probe.classify_probe_response(200, "[]")
        assert state.name == "EMPTY" and n == 0

    def test_404_is_no_board(self):
        state, _ = probe.classify_probe_response(404, "not found")
        assert state.name == "NO_BOARD"

    @pytest.mark.parametrize("status", [403, 429, 500])
    def test_http_errors_fetch_failed(self, status):
        state, _ = probe.classify_probe_response(status, "blocked")
        assert state.name == "FETCH_FAILED"

    def test_non_json_body_fetch_failed(self):
        state, _ = probe.classify_probe_response(200, "<html>waf</html>")
        assert state.name == "FETCH_FAILED"


# ── 探测 → 注册表升级 ──────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _registry(engine, ats_type, slug, status="UNVERIFIED", verified_at=None):
    with Session(engine) as s:
        row = JobAtsRegistry(company_name=f"Co-{slug}", ats_type=ats_type,
                             board_slug=slug, status=status,
                             verified_at=verified_at)
        s.add(row)
        s.commit()
        return row.id


def _rows(engine, ids):
    with Session(engine) as s:
        return s.scalars(select(JobAtsRegistry).where(
            JobAtsRegistry.id.in_(ids))).all()


def _session(engine):
    return Session(engine)


class TestProbeUpgrade:
    def test_200_n_upgrades_verified(self, db):
        rid = _registry(db, "greenhouse", "stripe")
        client = FakeClient({("greenhouse", "stripe"):
                             FakeResponse(200, json.dumps({"jobs": [1, 2]}))})
        rows = _rows(db, [rid])
        reports = probe.run_probe(rows, client=client)
        summary = probe.apply_results(_session(db), rows, reports, resync=False)
        assert summary["verified"] == 1
        row = _rows(db, [rid])[0]
        assert row.status == "VERIFIED"
        assert row.ats_type == "greenhouse"
        assert row.verified_at is not None

    def test_200_empty_also_verified(self, db):
        """EMPTY 也是 board 存在 → VERIFIED。"""
        rid = _registry(db, "lever", "emptyboard")
        client = FakeClient({("lever", "emptyboard"): FakeResponse(200, "[]")})
        rows = _rows(db, [rid])
        reports = probe.run_probe(rows, client=client)
        probe.apply_results(_session(db), rows, reports, resync=False)
        assert _rows(db, [rid])[0].status == "VERIFIED"

    def test_404_stays_unverified(self, db):
        rid = _registry(db, "greenhouse", "ghost")
        rows = _rows(db, [rid])
        reports = probe.run_probe(rows, client=FakeClient())  # 默认全 404
        summary = probe.apply_results(_session(db), rows, reports, resync=False)
        assert summary["verified"] == 0
        assert _rows(db, [rid])[0].status == "UNVERIFIED"

    def test_timeout_fetch_failed_stays_unverified(self, db, monkeypatch):
        from job_crawler.contracts import FetchState
        rid = _registry(db, "greenhouse", "slow")
        monkeypatch.setattr(probe, "probe_endpoint",
                            lambda c, a, s: (FetchState.FETCH_FAILED, 0))
        rows = _rows(db, [rid])
        reports = probe.run_probe(rows, client=FakeClient())
        probe.apply_results(_session(db), rows, reports, resync=False)
        assert _rows(db, [rid])[0].status == "UNVERIFIED"

    def test_resync_404_marks_dead(self, db):
        old = datetime.utcnow() - timedelta(days=90)
        rid = _registry(db, "greenhouse", "gone", status="VERIFIED",
                        verified_at=old)
        rows = _rows(db, [rid])
        reports = probe.run_probe(rows, client=FakeClient())  # 全 404
        summary = probe.apply_results(_session(db), rows, reports, resync=True)
        assert summary["dead"] == 1
        assert _rows(db, [rid])[0].status == "DEAD"


# ── 种子灌库幂等 ───────────────────────────────────────────────────────────

class TestLoadSeed:
    def test_upsert_idempotent(self, db):
        maker = sessionmaker(bind=db)

        with maker() as s:
            first = seed.load_seed(s)
        with maker() as s:
            second = seed.load_seed(s)
            total = len(s.scalars(select(JobAtsRegistry)).all())

        assert first["inserted"] == 13 and first["updated"] == 0
        assert second["inserted"] == 0 and second["updated"] == 13
        assert total == 13  # 幂等：重复灌库不重复插入

    def test_upsert_does_not_downgrade_status(self, db):
        rid = _registry(db, "greenhouse", "stripe", status="VERIFIED",
                        verified_at=datetime.utcnow())
        maker = sessionmaker(bind=db)
        with maker() as s:
            seed.load_seed(s)
        row = _rows(db, [rid])[0]
        assert row.status == "VERIFIED"  # 不降级
        assert row.verified_at is not None
