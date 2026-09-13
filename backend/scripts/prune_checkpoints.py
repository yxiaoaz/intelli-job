"""checkpoint 保留策略清理脚本（agent-context-overhaul Phase 5.3）

⚠️ 为什么不是"按 thread 保留最近 K 个 checkpoint"：
`AsyncPostgresSaver` **没有实现** `aprune`（`langgraph-checkpoint-postgres 3.1.2`
实测：`aprune` / `adelete_for_runs` / `acopy_thread` 只有 `BaseCheckpointSaver` 的
`raise NotImplementedError`，仅 `adelete_thread` 有真实实现）。而且基类文档明确警告：
`messages` 走 DeltaChannel，只按"keep_latest"删中间 checkpoint 会**截断父链**，
被保留的那条反而重建出空历史且**不报错**（`langgraph/checkpoint/base/__init__.py:387-413`）。

所以本脚本只做一件安全的事：**整 thread 删除**（`adelete_thread`），
两种目标：
  1. 孤儿 thread：`checkpoints.thread_id` 在 `chat_sessions` 里已不存在
     （会话被删但 checkpoint 残留，历史上攒下的那批）
  2. TTL：会话本身 `updated_at` 超过 N 天未活跃（默认关闭，需显式传 --ttl-days）

用法:
  python scripts/prune_checkpoints.py --dry-run                # 仅打印（默认）
  python scripts/prune_checkpoints.py --execute                # 清理孤儿 thread
  python scripts/prune_checkpoints.py --execute --ttl-days 90  # 连 90 天不活跃的会话一起清

幂等：可重复执行，第二次应为 0。建议接 cron（如每周一次 --dry-run 观察体积）。
副作用提醒：`init_checkpointer()` 会顺带跑一次 `saver.setup()`（与应用启动行为一致，
幂等），所以首次运行可能“顺便”建出 checkpoint 四张空表。

注：Windows 本地跑需要 Selector 事件循环（psycopg async 不兼容默认 ProactorEventLoop），
本脚本已自行处理；生产 Docker（Linux）无此问题。
"""
import argparse
import asyncio
import selectors
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv

load_dotenv(Path(backend_dir) / ".env")

from sqlalchemy import select, text  # noqa: E402

from app.core.checkpointer_factory import (  # noqa: E402
    close_checkpointer,
    get_checkpointer,
    init_checkpointer,
)
from app.database import AsyncSessionLocal  # noqa: E402
from app.models import ChatSession  # noqa: E402


async def _collect_targets(session, ttl_days: int) -> tuple[list[str], list[str]]:
    """返回 (孤儿 thread_id, TTL 过期 thread_id)"""
    result = await session.execute(text("SELECT DISTINCT thread_id FROM checkpoints"))
    threads = [row[0] for row in result.fetchall()]
    if not threads:
        return [], []

    # 仍存在的会话
    known_result = await session.execute(
        select(ChatSession.id).where(ChatSession.id.in_(_as_uuids(threads)))
    )
    known = {str(r[0]) for r in known_result.fetchall()}
    orphans = [t for t in threads if t not in known]

    expired: list[str] = []
    if ttl_days > 0:
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)
        stale_result = await session.execute(
            select(ChatSession.id, ChatSession.updated_at).where(
                ChatSession.id.in_(_as_uuids([t for t in threads if t in known])),
                ChatSession.updated_at < cutoff,
            )
        )
        expired = [str(r[0]) for r in stale_result.fetchall()]

    return orphans, expired


def _as_uuids(values: list[str]):
    """asyncpg 需要真正的 UUID 参数，传字符串会类型不匹配"""
    import uuid

    out = []
    for v in values:
        try:
            out.append(uuid.UUID(str(v)))
        except (ValueError, AttributeError, TypeError):
            continue  # 非 UUID 形态的 thread_id（如手动测试留下的）→ 归为孤儿
    return out


async def main(execute: bool, ttl_days: int):
    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"===== prune_checkpoints ({mode}, ttl_days={ttl_days}) =====")

    await init_checkpointer()
    saver = get_checkpointer()
    if saver is None:
        print("checkpointer 未启用（ENABLE_AGENT_CHECKPOINTER=False），无需清理")
        return

    try:
        async with AsyncSessionLocal() as session:
            try:
                orphans, expired = await _collect_targets(session, ttl_days)
            except Exception as e:  # noqa: BLE001
                print(f"读取 checkpoint 失败（表可能尚未创建，应用还没启动过）：{e}")
                return

        targets = list(dict.fromkeys(orphans + expired))
        print(f"孤儿 thread: {len(orphans)}    TTL 过期: {len(expired)}    合计待删: {len(targets)}")

        if not targets:
            print("无变更，幂等退出")
            return

        if not execute:
            for t in targets[:20]:
                print(f"[preview] adelete_thread({t})")
            if len(targets) > 20:
                print(f"... 另有 {len(targets) - 20} 条")
            print("确认无误后执行: python scripts/prune_checkpoints.py --execute")
            return

        for t in targets:
            await saver.adelete_thread(t)
            print(f"[deleted] {t}")
        print(f"\n完成: 删除 {len(targets)} 个 thread 的 checkpoint")
    finally:
        await close_checkpointer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="checkpoint 保留策略清理（整 thread 删除）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="仅打印待删清单（默认）")
    group.add_argument("--execute", action="store_true", help="执行删除")
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=0,
        help="连带清理 N 天未活跃的会话（0=关闭，只清孤儿 thread）",
    )
    args = parser.parse_args()

    if sys.platform == "win32":
        # psycopg async 无法跑在 Windows 默认的 ProactorEventLoop 上
        asyncio.run(
            main(execute=args.execute, ttl_days=args.ttl_days),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    else:
        asyncio.run(main(execute=args.execute, ttl_days=args.ttl_days))
