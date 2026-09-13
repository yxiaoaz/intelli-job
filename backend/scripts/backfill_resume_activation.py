"""
存量简历激活回填脚本（ui-review 回归 P0-2 收尾）

背景：
  "解析成功后自动激活"仅对部署后新上传/新解析的简历生效，
  存量用户的简历 active_status=False 且从未生成 profile.md，
  导致 agent 报"没有任何简历文件"、AI 解释被"请先上传简历"拦截。

做什么（对每个用户）：
  1. extracted_content 回填：优先从最新 status=completed 的 ResumeAnalysis
     写回 Resume.extracted_content（与 backfill_extracted_content.py 同逻辑）。
  2. 激活互斥：激活"有 extracted_content 的最新一份"（而非盲选最新上传），
     其余全部置 False。
  3. 记忆同步：将激活简历的解析结果写入 UserMemory.stable_facts 并
     write_user_memory（write-through 会同时生成 profile.md）。

幂等：可重复执行，重复运行无 diff。

用法:
  python scripts/backfill_resume_activation.py --dry-run   # 仅打印变更预览（默认）
  python scripts/backfill_resume_activation.py --execute   # 执行写入
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

from sqlalchemy import select, desc

from app.database import AsyncSessionLocal
from app.models import Resume, ResumeAnalysis
from app.utils.logger import get_logger

logger = get_logger()


def _extract_stable_facts(parsed_data: dict) -> dict:
    """从简历解析结果提取 stable_facts（与 app.api.v1.resumes 同逻辑）"""
    facts: dict = {}
    work_exp = parsed_data.get("work_experience", [])
    if work_exp and isinstance(work_exp, list) and len(work_exp) > 0:
        latest = work_exp[0]
        if isinstance(latest, dict):
            title = latest.get("title") or latest.get("position")
            company = latest.get("company")
            if title:
                facts["current_title"] = f"{title} @ {company}" if company else title
    education = parsed_data.get("education", [])
    if education and isinstance(education, list) and len(education) > 0:
        highest = education[0]
        if isinstance(highest, dict):
            parts = [p for p in [highest.get("school"), highest.get("degree"), highest.get("major")] if p]
            if parts:
                facts["education_level"] = " - ".join(parts)
    skills = parsed_data.get("skills", [])
    if skills and isinstance(skills, list):
        facts["skills"] = ", ".join(skills[:10])
    return facts


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


async def backfill_resume_activation(session, base_dir, execute: bool) -> int:
    """激活互斥 + memory/profile.md 同步，返回变更的用户数。

    独立函数供测试导入复用。
    """
    from app.memory.service import MemoryService
    from app.memory.schemas import UserMemory

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
            continue
        target = with_content[0]

        current_active = [r for r in user_resumes if r.active_status]
        need_activate = current_active != [target]
        profile_path = Path(base_dir) / f"user-{user_id}" / "profile.md"
        if not need_activate:
            # 已激活正确简历：memory 有技能事实且 profile.md 已存在才跳过
            # （DB 与文件系统分属两处，服务器重跑时靠文件存在性判定）
            mem_service = MemoryService(session, base_dir=base_dir)
            user_mem = await mem_service.get_user_memory(user_id)
            if user_mem and user_mem.stable_facts.get("skills") and profile_path.exists():
                continue

        print(
            f"[activation] user_id={user_id} -> resume_id={target.id} "
            f"filename={target.filename!r} "
            f"(prev_active={[r.id for r in current_active]})"
        )
        if execute:
            for r in user_resumes:
                r.active_status = r.id == target.id
            await session.commit()
            mem_service = MemoryService(session, base_dir=base_dir)
            user_mem = await mem_service.get_user_memory(user_id) or UserMemory()
            stable_facts = _extract_stable_facts(target.extracted_content or {})
            if stable_facts:
                user_mem.stable_facts.update(stable_facts)
            # write_user_memory 是 write-through：同时生成 profile.md
            await mem_service.write_user_memory(user_id, user_mem)
            print(
                f"[memory] user_id={user_id} stable_facts 已同步, "
                f"profile.md 已生成: {Path(base_dir) / f'user-{user_id}' / 'profile.md'}"
            )
        changed_users += 1

    return changed_users


async def main(execute: bool):
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"===== backfill_resume_activation ({mode}) =====")

    from app.services.intent_file_service import IntentFileService

    base_dir = str(IntentFileService().base_dir)

    async with AsyncSessionLocal() as session:
        n1 = await _backfill_extracted_content(session, execute)
        n2 = await backfill_resume_activation(session, base_dir, execute)

        if execute:
            await session.commit()
            print(f"\n完成: extracted_content 回填 {n1} 条, 激活/同步用户 {n2} 个")
        else:
            await session.rollback()
            print(f"\n(DRY-RUN) 预计: extracted_content 回填 {n1} 条, 激活/同步用户 {n2} 个")
            print("确认无误后执行: python scripts/backfill_resume_activation.py --execute")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="存量简历激活 + profile.md 回填")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="仅打印变更预览（默认）")
    group.add_argument("--execute", action="store_true", help="执行写入")
    args = parser.parse_args()

    asyncio.run(main(execute=args.execute))
