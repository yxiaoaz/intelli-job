# -*- coding: utf-8 -*-
"""历史指纹回填脚本（job-source-adapter-refactor Phase 2.2）。

将 job_items 全表指纹从 uuid3(url) 切换为跨源算法
sha1(norm(company)|norm(title)|norm(location))。三步，幂等：

  1. --dry-run：全表重算，冲突组清单写 backfill_report_<date>.json（不写库）
  2. --apply  ：冲突组保留 update_time 最大者；先按 id 删 Milvus、再删 SQL，
                事务包裹；然后把全部保留行指纹更新为新算法值
  3. 输出执行摘要（删除行数 / 保留行数 / 指纹更新行数）

幂等：重复执行时冲突组为 0、指纹更新行为 0，无副作用。

用法（backend 目录，venv）：
  python scripts/backfill_fingerprint.py --dry-run
  python scripts/backfill_fingerprint.py --apply
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import delete as sqlalchemy_delete, select, update as sqlalchemy_update  # noqa: E402

from app.models import JobItem  # noqa: E402
from app.services.crawler_db_controller import CrawlerDBController  # noqa: E402
from app.utils.logger import get_logger, setup_logging  # noqa: E402
from job_crawler.contracts import compute_fingerprint  # noqa: E402

logger = get_logger()

EPOCH_MIN = datetime.min


def _incomplete(job: JobItem) -> dict:
    """字段完整率标记：salary/description 为空或占位值视为不完整。"""
    salary = (job.salary or "").strip()
    desc = (job.description or "").strip()
    return {
        "salary_ok": salary not in ("", "NA", "未知"),
        "description_ok": desc not in ("", "未知"),
    }


def _row_view(job: JobItem, keep: bool) -> dict:
    return {
        "id": str(job.id),
        "url": job.url,
        "job_title": job.job_title,
        "company_name": job.company_name,
        "location": job.location,
        "update_time": job.update_time.isoformat() if job.update_time else None,
        "keep": keep,
        **_incomplete(job),
    }


def analyze():
    """全表重算指纹，返回 (rows, conflict_groups)。

    conflict_groups: [{new_fingerprint, keeper(JobItem), losers[JobItem]}]
    """
    controller = CrawlerDBController()
    with controller.session_maker() as session:
        rows = session.scalars(select(JobItem)).all()

    groups: dict[str, list[JobItem]] = defaultdict(list)
    for row in rows:
        new_fp = compute_fingerprint(row.company_name, row.job_title, row.location)
        groups[new_fp].append(row)

    conflict_groups = []
    for new_fp, members in groups.items():
        if len(members) < 2:
            continue
        keeper = max(members, key=lambda r: r.update_time or EPOCH_MIN)
        losers = [r for r in members if r.id != keeper.id]
        conflict_groups.append({
            "new_fingerprint": new_fp,
            "keeper": keeper,
            "losers": losers,
        })
    return rows, conflict_groups


def dry_run(rows, conflict_groups) -> Path:
    report_path = BACKEND_DIR / "scripts" / (
        f"backfill_report_{datetime.now().strftime('%Y%m%d')}.json")
    loser_total = sum(len(g["losers"]) for g in conflict_groups)
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_rows": len(rows),
        "conflict_groups": len(conflict_groups),
        "rows_to_delete": loser_total,
        "groups": [
            {
                "new_fingerprint": g["new_fingerprint"],
                "keeper": _row_view(g["keeper"], keep=True),
                "losers": [_row_view(r, keep=False) for r in g["losers"]],
            }
            for g in conflict_groups
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    logger.info(f"[dry-run] 总行数={len(rows)} 冲突组={len(conflict_groups)} "
                f"将删除={loser_total} 报告={report_path}")
    return report_path


def apply(rows, conflict_groups) -> dict:
    loser_ids = [r.id for g in conflict_groups for r in g['losers']]

    # 1. 先删 Milvus（按 id，走 VectorDBService 删除路径）；不存在 id 无副作用
    if loser_ids:
        from app.services.vector_db_service import VectorDBService

        vector_db = VectorDBService()
        vector_db.delete_embeddings_by_ids(loser_ids)

    # 2. 删 SQL + 更新保留行指纹：分块事务（广域网下单事务逐行 ORM 提交过慢）
    controller = CrawlerDBController()
    updated_fingerprints = 0
    total_rows_before = len(rows)
    CHUNK = 1000
    with controller.session_maker() as session:
        for start in range(0, len(loser_ids), CHUNK):
            chunk = loser_ids[start:start + CHUNK]
            session.execute(
                sqlalchemy_delete(JobItem).where(JobItem.id.in_(chunk)))
            session.commit()
            logger.info(f"[apply] deleted {min(start + CHUNK, len(loser_ids))}"
                        f"/{len(loser_ids)}")

        # 全表重算指纹，分块 executemany 更新（每块一次往返，仅更新有变化的行）
        with controller.session_maker() as session:
            all_rows = session.execute(
                select(JobItem.id, JobItem.fingerprint, JobItem.company_name,
                       JobItem.job_title, JobItem.location)).all()
        updates = []
        for row_id, old_fp, company, title, location in all_rows:
            new_fp = compute_fingerprint(company, title, location)
            if old_fp != new_fp:
                updates.append({"id": row_id, "fingerprint": new_fp})

        for start in range(0, len(updates), CHUNK):
            chunk = updates[start:start + CHUNK]
            try:
                session.execute(sqlalchemy_update(JobItem), chunk)
                session.commit()
                updated_fingerprints += len(chunk)
            except Exception:
                # 并发插入可能产生新的同指纹行（UNIQUE 冲突）：降级为逐行，
                # 冲突行跳过，留待下一次幂等执行由冲突组逻辑收敛
                session.rollback()
                for u in chunk:
                    try:
                        session.execute(
                            sqlalchemy_update(JobItem)
                            .where(JobItem.id == u["id"])
                            .values(fingerprint=u["fingerprint"]))
                        session.commit()
                        updated_fingerprints += 1
                    except Exception:
                        session.rollback()
                        logger.warning(
                            f"[apply] fingerprint update skipped for "
                            f"{u['id']} (concurrent conflict)")
            logger.info(f"[apply] fingerprint updated "
                        f"{min(start + CHUNK, len(updates))}/{len(updates)}")

    summary = {
        "total_rows_before": total_rows_before,
        "deleted": len(loser_ids),
        "kept": len(all_rows),
        "fingerprints_updated": updated_fingerprints,
    }
    logger.info(f"[apply] 删除={summary['deleted']} 保留={summary['kept']} "
                f"指纹更新={summary['fingerprints_updated']}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="历史指纹回填（幂等）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="只输出冲突组报告，不写库")
    mode.add_argument("--apply", action="store_true",
                      help="执行删除与指纹更新（先人工确认 dry-run 报告）")
    args = parser.parse_args()

    rows, conflict_groups = analyze()
    if args.dry_run:
        dry_run(rows, conflict_groups)
        return

    summary = apply(rows, conflict_groups)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    setup_logging()
    main()
