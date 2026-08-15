"""chat_end_reconcile — 被动 reconcile 兜底。

chat 流程结束时调用：比对 markdown mtime 与 DB last_updated。
如果 markdown 比 DB 新 → parse markdown → upsert DB。
不阻塞主流程：失败 log warning + 跳过。
"""
import asyncio
import os
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.markdown_renderer import parse_session_memory
from app.repositories.session_memory_repo import SessionMemoryRepository
from app.utils.logger import get_logger

logger = get_logger()


async def chat_end_reconcile(
    db: AsyncSession,
    user_id: UUID,
    thread_id: str,
    markdown_path: str,
) -> None:
    """chat 流程结束时调用：比对 markdown mtime 与 DB last_updated。

    如果 markdown 比 DB 新 → parse markdown → upsert DB。
    不阻塞主流程：失败 log warning + 跳过。
    """
    try:
        # 1. 检查 markdown 文件是否存在
        if not os.path.exists(markdown_path):
            return

        # 2. 读 markdown mtime
        markdown_mtime = datetime.fromtimestamp(os.path.getmtime(markdown_path))

        # 3. 读 DB last_updated_at
        session_repo = SessionMemoryRepository(db)
        db_record = await session_repo.get_by_thread(thread_id)

        if not db_record:
            # DB 没有记录 → 从 markdown 创建
            content = await asyncio.to_thread(
                lambda: open(markdown_path, "r", encoding="utf-8").read()
            )
            parsed = parse_session_memory(content)
            if parsed:
                await session_repo.upsert(thread_id, user_id, parsed)
                await db.commit()
                logger.info("chat_end_reconcile_created", thread_id=thread_id)
            return

        # 4. 比对时间
        if db_record.last_updated and markdown_mtime > db_record.last_updated:
            # markdown 比 DB 新 → 用 markdown 覆盖 DB
            content = await asyncio.to_thread(
                lambda: open(markdown_path, "r", encoding="utf-8").read()
            )
            parsed = parse_session_memory(content)
            if parsed:
                await session_repo.upsert(thread_id, user_id, parsed)
                await db.commit()
                logger.info("chat_end_reconcile_updated", thread_id=thread_id)
            else:
                logger.warning("chat_end_reconcile_parse_failed", thread_id=thread_id)
        else:
            logger.debug("chat_end_reconcile_skipped", thread_id=thread_id)

    except Exception as e:
        logger.warning("chat_end_reconcile_failed", thread_id=thread_id, error=str(e))
