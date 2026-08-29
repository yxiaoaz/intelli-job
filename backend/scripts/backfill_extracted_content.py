"""
存量数据回填脚本：Resume.extracted_content + active_status 修复

用途（resume-profile-hub 变更 Phase 1.4）：
  1. extracted_content 回填：Resume.extracted_content 曾从未写入，
     遍历所有 Resume，取其最新 status=completed 的 ResumeAnalysis.parsed_data 写入。
  2. active_status 修复：每用户至多一份激活简历——
     多激活时保留 uploaded_at 最新的一份，其余置 False；
     零激活但有简历时激活最新一份。

幂等：可重复执行，重复运行无 diff。

用法:
  python scripts/backfill_extracted_content.py --dry-run   # 仅打印变更预览（默认）
  python scripts/backfill_extracted_content.py --execute   # 执行写入
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

# 修复 Windows GBK 编码问题
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 添加 backend 目录到 Python 路径
backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from sqlalchemy import select, func, desc

from app.database import AsyncSessionLocal
from app.models import Resume, ResumeAnalysis
from app.utils.logger import get_logger

logger = get_logger()


async def backfill_extracted_content(session, execute: bool) -> int:
    """回填 extracted_content，返回变更数量"""
    result = await session.execute(select(Resume).order_by(Resume.uploaded_at))
    resumes = result.scalars().all()

    changed = 0
    for resume in resumes:
        # 最新 completed 分析记录
        analysis_result = await session.execute(
            select(ResumeAnalysis)
            .where(
                ResumeAnalysis.resume_id == resume.id,
                ResumeAnalysis.status == "completed",
            )
            .order_by(desc(ResumeAnalysis.created_at))
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()

        if not analysis or not analysis.parsed_data:
            continue

        if resume.extracted_content == analysis.parsed_data:
            continue  # 已一致，幂等跳过

        # diff 预览
        parsed = analysis.parsed_data or {}
        skills = parsed.get("skills") or []
        work = parsed.get("work_experience") or []
        title = ""
        if work and isinstance(work, list) and isinstance(work[0], dict):
            title = work[0].get("position") or work[0].get("title") or ""
        print(
            f"[extracted_content] resume_id={resume.id} "
            f"filename={resume.filename!r} title={title!r} skills_count={len(skills)} "
            f"old={'NULL' if not resume.extracted_content else 'differs'}"
        )

        if execute:
            resume.extracted_content = analysis.parsed_data
            resume.parsed_at = analysis.created_at
            changed += 1

    return changed


async def fix_active_status(session, execute: bool) -> int:
    """修复 active_status 互斥，返回变更数量"""
    # 每用户的简历按 uploaded_at 降序
    result = await session.execute(
        select(Resume).order_by(Resume.user_id, desc(Resume.uploaded_at))
    )
    resumes = result.scalars().all()

    by_user: dict = {}
    for r in resumes:
        by_user.setdefault(r.user_id, []).append(r)

    changed = 0
    for user_id, user_resumes in by_user.items():
        activated = [r for r in user_resumes if r.active_status]

        if len(activated) > 1:
            # 保留最新一份（列表已按 uploaded_at 降序，第一个即最新）
            keep = activated[0]
            for r in activated[1:]:
                print(
                    f"[active_status] user_id={user_id} resume_id={r.id} "
                    f"multi-active -> False (keep {keep.id})"
                )
                if execute:
                    r.active_status = False
                    changed += 1

        elif len(activated) == 0 and user_resumes:
            # 零激活：激活最新一份
            latest = user_resumes[0]
            print(
                f"[active_status] user_id={user_id} resume_id={latest.id} "
                f"zero-active -> True"
            )
            if execute:
                latest.active_status = True
                changed += 1

    return changed


async def main(execute: bool):
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"===== backfill_extracted_content ({mode}) =====")

    async with AsyncSessionLocal() as session:
        # 总量统计
        total = await session.scalar(select(func.count()).select_from(Resume))
        print(f"简历总数: {total}")

        n1 = await backfill_extracted_content(session, execute)
        n2 = await fix_active_status(session, execute)

        if execute:
            await session.commit()
            print(f"\n完成: extracted_content 写回 {n1} 条, active_status 修复 {n2} 条")
        else:
            await session.rollback()
            print(f"\n(DRY-RUN) 预计: extracted_content 写回 {n1} 条, active_status 修复 {n2} 条")
            print("确认无误后执行: python scripts/backfill_extracted_content.py --execute")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume extracted_content / active_status 回填")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="仅打印变更预览（默认）")
    group.add_argument("--execute", action="store_true", help="执行写入")
    args = parser.parse_args()

    asyncio.run(main(execute=args.execute))
