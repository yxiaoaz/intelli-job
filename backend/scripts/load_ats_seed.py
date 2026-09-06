# -*- coding: utf-8 -*-
"""ATS 映射种子灌库（ats-job-source-integration Phase 1.1）。

读取 scripts/data/ats_registry_seed.json，按 (ats_type, board_slug) upsert：
- 已存在 → 仅更新 company_name/careers_url（不降级 status/verified_at）
- 不存在 → 插入，status=UNVERIFIED（由 probe_ats_boards.py 首跑升级）

用法（backend 目录，venv）：
  python scripts/load_ats_seed.py
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select  # noqa: E402

from app.models import JobAtsRegistry  # noqa: E402
from app.services.crawler_db_controller import CrawlerDBController  # noqa: E402
from app.utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger()

SEED_PATH = BACKEND_DIR / "scripts" / "data" / "ats_registry_seed.json"


def load_seed(session) -> dict:
    entries = json.loads(SEED_PATH.read_text(encoding="utf-8"))["entries"]
    inserted, updated = 0, 0
    for entry in entries:
        row = session.scalar(select(JobAtsRegistry).where(
            JobAtsRegistry.ats_type == entry["ats_type"],
            JobAtsRegistry.board_slug == entry["board_slug"],
        ))
        if row is None:
            session.add(JobAtsRegistry(
                company_name=entry["company_name"],
                ats_type=entry["ats_type"],
                board_slug=entry["board_slug"],
                careers_url=entry.get("careers_url"),
                status="UNVERIFIED",
            ))
            inserted += 1
        else:
            row.company_name = entry["company_name"]
            row.careers_url = entry.get("careers_url")
            updated += 1
    session.commit()
    return {"inserted": inserted, "updated": updated, "total": len(entries)}


def main():
    controller = CrawlerDBController()
    with controller.session_maker() as session:
        summary = load_seed(session)
    logger.info(f"[load_ats_seed] inserted={summary['inserted']} "
                f"updated={summary['updated']} total={summary['total']}")
    print(summary)


if __name__ == "__main__":
    setup_logging()
    main()
