"""Resume 查询辅助 — 全站唯一的「当前激活简历」取法。

背景（agent-context-overhaul E2E 验收发现）：`resumes.active_status` 的互斥不变量
曾被 seed / 回填流程打破（同一用户名下存在多行 active），而此前 5 处调用各自写
`select(Resume).where(user_id, active_status).limit(1)` 且**不带排序**，数据库返回
哪一份不确定 —— 于是 agent 读到的简历（DbBackend 按 parsed_at 倒序取）与岗位匹配、
AI 解释用的简历可能不是同一份。统一走本函数消除口径分叉。
"""

from __future__ import annotations

import uuid
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resume


async def get_active_resume(
    db: AsyncSession, user_id: Union[str, uuid.UUID, None]
) -> Optional[Resume]:
    """取用户当前激活的简历；多行 active 时按解析时间最新的那份优先。

    Args:
        db: 调用方已打开的 AsyncSession（提交/关闭由调用方负责）
        user_id: UUID 或其字符串形式（agent 工具链路里拿到的是 str）

    Returns:
        Resume ORM 实例；无激活简历或 user_id 为空时返回 None
    """
    if not user_id:
        return None

    uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == uid, Resume.active_status.is_(True))
        # parsed_at 为 NULL（从未解析成功）的行排到最后。不直接写
        # `parsed_at.desc().nulls_last()`：Postgres 下 DESC 默认 NULLS FIRST，
        # 而 SQLite 默认相反，用布尔表达式排序可保证两端一致。
        .order_by(Resume.parsed_at.is_(None), Resume.parsed_at.desc())
        .limit(1)
    )
    return result.scalars().first()
