"""
存量简历 extracted_content 回填 + 激活互斥修复脚本

背景：
  "解析成功后自动激活"仅对部署后新上传/新解析的简历生效，存量用户的简历
  active_status=False（甚至多份同时 True），导致 agent 读不到简历、
  AI 解释被"请先上传简历"拦截。

做什么（对每个用户）：
  1. extracted_content 回填：优先从最新 status=completed 的 ResumeAnalysis
     写回 Resume.extracted_content（与 backfill_extracted_content.py 同逻辑）。
  2. 激活互斥：激活"有 extracted_content 的最新一份"（而非盲选最新上传），
     其余全部置 False。

原第 3 步（写入 UserMemory.stable_facts 并生成 profile.md）已随
agent-context-overhaul Phase 3 退役：stable_facts 列被 drop，
`/memory/profile.md` 与 `/resume/active.md` 都由 DbBackend 按需从 DB 渲染，
不再有"落盘投影"需要回填。

幂等：可重复执行，重复运行无 diff。

用法:
  python scripts/backfill_resume_activation.py --dry-run   # 仅打印变更预览（默认）
  python scripts/backfill_resume_activation.py --execute   # 执行写入
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 修复 Windows GBK 编码问题
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 添加 backend 目录到 Python 路径
backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv

load_dotenv(Path(backend_dir) / ".env")

from sqlalchemy import select, desc

from app.database import AsyncSessionLocal
from app.models import Resume, ResumeAnalysis
from app.utils.logger import get_logger

logger = get_logger()


async def _backfill_extracted_content(session, execute: bool) -> int:
    """回填 extracted_content（从最新 completed 分析），返回变更数量"""
    result = await session.execute(select(Resume).order_by(Resume.uploaded_at))
    resumes = result.scalars().all()

    changed = 0
    for resume in resumes:
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

        print(
            f"[extracted_content] resume_id={resume.id} filename={resume.filename!r} "
            f"old={'NULL' if not resume.extracted_content else 'differs'} -> 回填"
        )
        # 无论 dry-run/execute 都先在内存中应用，让后续激活预览能看到
        # 真实计划（dry-run 结束后 main() 会 rollback，不会落库）
        resume.extracted_content = analysis.parsed_data
        resume.parsed_at = analysis.created_at
        changed += 1
    return changed


async def backfill_resume_activation(session, execute: bool) -> int:
    """修复激活互斥，返回变更的用户数。

    独立函数供测试导入复用。
    """
    result = await session.execute(
        select(Resume).order_by(Resume.user_id, desc(Resume.uploaded_at))
    )
    resumes = result.scalars().all()

    by_user: dict = {}
    for r in resumes:
        by_user.setdefault(r.user_id, []).append(r)

    changed_users = 0
    for user_id, user_resumes in by_user.items():
        # 候选：有 extracted_content 的简历（列表已按 uploaded_at 降序）
        with_content = [r for r in user_resumes if r.extracted_content]
        if not with_content:
            print(f"[skip] user_id={user_id} 没有任何已解析出内容的简历")
            continue
        target = with_content[0]

        current_active = [r for r in user_resumes if r.active_status]
        if current_active == [target]:
            continue  # 已激活正确简历，幂等跳过

        print(
            f"[activation] user_id={user_id} -> resume_id={target.id} "
            f"filename={target.filename!r} "
            f"(prev_active={[r.id for r in current_active]})"
        )
        if execute:
            for r in user_resumes:
                r.active_status = r.id == target.id
            await session.commit()
        changed_users += 1

    return changed_users


async def main(execute: bool):
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"===== backfill_resume_activation ({mode}) =====")

    async with AsyncSessionLocal() as session:
        n1 = await _backfill_extracted_content(session, execute)
        n2 = await backfill_resume_activation(session, execute)

        if execute:
            await session.commit()
            print(f"\n完成: extracted_content 回填 {n1} 条, 激活修正 {n2} 个用户")
        else:
            await session.rollback()
            print(
                f"\n(DRY-RUN) 预计: extracted_content 回填 {n1} 条, "
                f"激活修正 {n2} 个用户"
            )
            print("确认无误后执行: python scripts/backfill_resume_activation.py --execute")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="存量简历 extracted_content 回填 + 激活互斥修复")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="仅打印变更预览（默认）")
    group.add_argument("--execute", action="store_true", help="执行写入")
    args = parser.parse_args()

    asyncio.run(main(execute=args.execute))
