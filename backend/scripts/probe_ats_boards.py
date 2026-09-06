# -*- coding: utf-8 -*-
"""ATS board 探测脚本（ats-job-source-integration Phase 1.2）。

对注册表条目并发（≤4）探测 Greenhouse/Lever/Ashby 三端点，四态判别
（禁把 404 当零岗位）：
- OK（200 且 ≥1 条）或 EMPTY（200 且 0 条）→ board 存在，升 VERIFIED + verified_at
- NO_BOARD（404）→ UNVERIFIED 保持（--resync 模式下 VERIFIED 行 404 → 标 DEAD）
- FETCH_FAILED（超时/5xx/403/429/非 JSON）→ 记录不升级

礼貌探测：全局 ≥1s 间隔、≤4 并发。输出探测报告 JSON 供人工复核。

用法（backend 目录，venv）：
  python scripts/probe_ats_boards.py            # 探测 UNVERIFIED 行
  python scripts/probe_ats_boards.py --resync   # 复检 60 天未验证的 VERIFIED 行
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select  # noqa: E402

from app.models import JobAtsRegistry  # noqa: E402
from app.services.crawler_db_controller import CrawlerDBController  # noqa: E402
from app.utils.logger import get_logger, setup_logging  # noqa: E402
from job_crawler.contracts import FetchState  # noqa: E402

logger = get_logger()

ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
}
PROBE_ATS_TYPES = ["greenhouse", "lever", "ashby"]
CONCURRENCY = 4
MIN_INTERVAL_SECONDS = 1.0
RESYNC_INTERVAL_DAYS = 60

_rate_lock = threading.Lock()
_last_request_at = 0.0


def _throttle():
    """全局 ≥1s 间隔（礼貌探测）。"""
    global _last_request_at
    with _rate_lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def classify_probe_response(status: int, body: str) -> tuple[FetchState, int]:
    """四态判别 + 岗位数。404 ≠ 零岗位 ≠ 拉取失败。"""
    if status == 404:
        return FetchState.NO_BOARD, 0
    if status != 200:
        return FetchState.FETCH_FAILED, 0
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return FetchState.FETCH_FAILED, 0
    if isinstance(data, list):
        count = len(data)
    elif isinstance(data, dict):
        jobs = data.get("jobs", data.get("data"))
        count = len(jobs) if isinstance(jobs, list) else 0
    else:
        count = 0
    return (FetchState.OK if count > 0 else FetchState.EMPTY), count


def probe_endpoint(client, ats_type: str, slug: str) -> tuple[FetchState, int]:
    _throttle()
    url = ENDPOINTS[ats_type].format(slug=slug)
    try:
        resp = client.get(url, timeout=30.0)
    except Exception as e:
        logger.warning(f"[probe] {ats_type}/{slug} request failed: {e}")
        return FetchState.FETCH_FAILED, 0
    state, count = classify_probe_response(resp.status_code, resp.text)
    logger.info(f"[probe] {ats_type}/{slug} -> {state.value} (n={count})")
    return state, count


def probe_company(client, row: JobAtsRegistry) -> dict:
    """对一家公司试三端点；命中 OK/EMPTY 即为 board 存在。"""
    results = {}
    hit = None
    for ats_type in PROBE_ATS_TYPES:
        state, count = probe_endpoint(client, ats_type, row.board_slug)
        results[ats_type] = {"state": state.value, "count": count}
        if hit is None and state in (FetchState.OK, FetchState.EMPTY):
            hit = ats_type
    return {"company_name": row.company_name, "board_slug": row.board_slug,
            "results": results, "hit": hit}


def run_probe(rows, client=None) -> list[dict]:
    """client 可注入（单测用 FakeClient），缺省自建 httpx 客户端。"""
    reports = []
    if client is None:
        client = httpx.Client(follow_redirects=False)
        try:
            return _run_pool(client, rows)
        finally:
            client.close()
    return _run_pool(client, rows)


def _run_pool(client, rows) -> list[dict]:
    reports = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(probe_company, client, r): r for r in rows}
        for future in as_completed(futures):
            reports.append(future.result())
    return reports


def apply_results(session, rows, reports, resync: bool) -> dict:
    # rows 可能来自其他 session（单测/调用方），在本 session 内重取以保证落库
    row_ids = [r.id for r in rows]
    db_rows = session.scalars(select(JobAtsRegistry).where(
        JobAtsRegistry.id.in_(row_ids))).all()
    by_slug = {(r.ats_type, r.board_slug): r for r in db_rows}
    verified, dead, unchanged = 0, 0, 0
    now = datetime.utcnow()
    for report in reports:
        row = None
        for (ats_type, slug), candidate in by_slug.items():
            if candidate.board_slug == report["board_slug"]:
                row = candidate
                break
        if row is None:
            continue
        if report["hit"]:
            row.status = "VERIFIED"
            row.verified_at = now
            row.ats_type = report["hit"]  # 探测命中即修正映射
            verified += 1
        elif resync and row.status == "VERIFIED":
            # 复检 404：board 已删除/公司换 ATS → DEAD
            all_no_board = all(
                v["state"] == "no_board" for v in report["results"].values())
            if all_no_board:
                row.status = "DEAD"
                dead += 1
            else:
                unchanged += 1
        else:
            unchanged += 1
    session.commit()
    return {"verified": verified, "dead": dead, "unchanged": unchanged}


def main():
    parser = argparse.ArgumentParser(description="ATS board 探测")
    parser.add_argument("--resync", action="store_true",
                        help=f"复检 {RESYNC_INTERVAL_DAYS} 天未验证的 VERIFIED 行")
    args = parser.parse_args()

    controller = CrawlerDBController()
    with controller.session_maker() as session:
        if args.resync:
            cutoff = datetime.utcnow() - timedelta(days=RESYNC_INTERVAL_DAYS)
            rows = session.scalars(select(JobAtsRegistry).where(
                JobAtsRegistry.status == "VERIFIED",
                JobAtsRegistry.verified_at < cutoff,
            )).all()
        else:
            rows = session.scalars(select(JobAtsRegistry).where(
                JobAtsRegistry.status == "UNVERIFIED")).all()

        logger.info(f"[probe] {len(rows)} rows to probe "
                    f"(mode={'resync' if args.resync else 'initial'})")
        reports = run_probe(rows)
        summary = apply_results(session, rows, reports, resync=args.resync)

    report_path = BACKEND_DIR / "scripts" / (
        f"ats_probe_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    report_path.write_text(json.dumps(
        {"mode": "resync" if args.resync else "initial",
         "summary": summary, "reports": reports},
        ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[probe] summary={summary} report={report_path}")


if __name__ == "__main__":
    setup_logging()
    main()
