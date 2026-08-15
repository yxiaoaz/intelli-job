"""MemoryService — 记忆系统业务边界。

负责：
- markdown + DB 双写（write-through）
- 冷启动（get_or_init）
- 粗粒度 merge（list append / scalar set）
"""
import asyncio
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.schemas import (
    UserMemory,
    SessionMemory,
    JobPreference,
)
from app.memory.markdown_renderer import (
    render_user_memory,
    render_session_memory,
)
from app.repositories.user_memory_repo import UserMemoryRepository
from app.repositories.session_memory_repo import SessionMemoryRepository
from app.utils.logger import get_logger

logger = get_logger()


class MemoryService:
    """记忆系统统一入口"""

    def __init__(self, db: AsyncSession, base_dir: str | Path):
        self.db = db
        self.base_dir = Path(base_dir)
        self.user_repo = UserMemoryRepository(db)
        self.session_repo = SessionMemoryRepository(db)

    def session_markdown_path(self, user_id: UUID, thread_id: str) -> Path:
        """返回 session markdown 文件路径（供 reconcile 等外部调用）"""
        return self.base_dir / f"user-{user_id}" / f"session-{thread_id}.md"

    # ── User Memory (L2) ──────────────────────────────────────────────────

    async def write_user_memory(self, user_id: UUID, payload: UserMemory) -> None:
        """write-through: 写 markdown + DB"""
        # 1. 渲染 markdown
        md = render_user_memory(payload)

        # 2. 写 markdown 文件
        user_dir = self.base_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        profile_path = user_dir / "profile.md"
        await asyncio.to_thread(profile_path.write_text, md, encoding="utf-8")

        # 3. 写 DB
        try:
            await self.user_repo.upsert(user_id, payload)
            await self.db.commit()
        except Exception as e:
            logger.warning("write_user_memory_db_failed", user_id=str(user_id), error=str(e))

    async def get_user_memory(self, user_id: UUID) -> Optional[UserMemory]:
        """从 DB 读用户长期记忆"""
        return await self.user_repo.get(user_id)

    async def merge_user_updates(self, current: UserMemory, updates: dict) -> UserMemory:
        """粗粒度 merge：list 字段 append，其他 set"""
        data = current.model_dump()

        for key, value in updates.items():
            if key not in data:
                continue
            old = data[key]
            if isinstance(old, list) and isinstance(value, list):
                combined = list(old)
                for item in value:
                    if item not in combined:
                        combined.append(item)
                data[key] = combined
            elif isinstance(old, dict) and isinstance(value, dict):
                # 嵌套 dict（如 long_term_preferences）→ 浅 merge
                old.update(value)
                data[key] = old
            elif value is not None:
                data[key] = value

        return UserMemory(**data)

    # ── Session Memory (L1) ───────────────────────────────────────────────

    async def write_session_memory(
        self, user_id: UUID, thread_id: str, payload: SessionMemory
    ) -> None:
        """write-through: 写 markdown + DB"""
        # 1. 渲染 markdown
        md = render_session_memory(payload)

        # 2. 写 markdown 文件
        user_dir = self.base_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        session_path = user_dir / f"session-{thread_id}.md"
        await asyncio.to_thread(session_path.write_text, md, encoding="utf-8")

        # 3. 写 DB
        try:
            await self.session_repo.upsert(thread_id, user_id, payload)
            await self.db.commit()
        except Exception as e:
            logger.warning("write_session_memory_db_failed", thread_id=thread_id, error=str(e))

    async def get_or_init_session_memory(
        self, user_id: UUID, thread_id: str
    ) -> SessionMemory:
        """冷启动：从 DB 拉，空就创建"""
        existing = await self.session_repo.get_by_thread(thread_id)
        if existing:
            return existing
        return SessionMemory()

    async def merge_session_updates(
        self, current: SessionMemory, updates: dict
    ) -> SessionMemory:
        """粗粒度 merge：list 字段 append，标量字段 set，JobPreference 嵌套 merge"""
        data = current.model_dump()

        # SessionMemory 的 list 字段
        list_fields = {"open_questions", "recent_decisions"}
        # JobPreference 嵌套字段
        pref_fields = {
            "target_roles", "locations", "recruitment_types",
            "industries", "skills", "target_companies", "target_company_types",
        }

        for key, value in updates.items():
            if key == "preferences" and isinstance(value, dict):
                # 嵌套 JobPreference merge
                prefs_data = data.get("preferences", {})
                for pk, pv in value.items():
                    if pk in pref_fields and isinstance(pv, list):
                        old_list = prefs_data.get(pk, [])
                        combined = list(old_list)
                        for item in pv:
                            if item not in combined:
                                combined.append(item)
                        prefs_data[pk] = combined
                    elif pv is not None:
                        prefs_data[pk] = pv
                data["preferences"] = prefs_data
            elif key in list_fields and isinstance(value, list):
                old = data.get(key, [])
                combined = list(old)
                for item in value:
                    if item not in combined:
                        combined.append(item)
                data[key] = combined
            elif key in data and value is not None:
                data[key] = value

        return SessionMemory(**data)
