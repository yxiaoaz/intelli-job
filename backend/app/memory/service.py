"""MemoryService — 记忆系统业务边界。

职责（agent-context-overhaul Phase 3 后）：
- L1 `session-*.md`：markdown + DB 双写（write-through）+ reconcile
- L2 `user_memories`：**只写 DB**。`/memory/profile.md` 是 DbBackend 实时渲染的只读视图，
  不再落盘，因此切换简历零成本、也不会出现文件/DB 分叉
- 冷启动（get_or_init）、粗粒度 merge、**多写入方仲裁（merge_with_source）**
"""
import asyncio
import os
from pathlib import Path
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.schemas import (
    UserMemory,
    SessionMemory,
    JobPreference,
)
from app.memory.markdown_renderer import (
    render_session_memory,
)
from app.repositories.user_memory_repo import UserMemoryRepository
from app.repositories.session_memory_repo import SessionMemoryRepository
from app.utils.logger import get_logger

logger = get_logger()

# L2 写入来源优先级（design.md「写入仲裁」）：
# 前端设置页显式设定 > 对话中 agent 抽取 > 简历自动抽取
PREFERENCE_SOURCE_PRIORITY: dict[str, int] = {"resume": 1, "agent": 2, "user": 3}


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
        """写 L2：只写 DB。

        原本这里是 write-through（渲染 markdown 落盘），但 profile.md 没有回写回路，
        属于"有去无回的投影"：切简历要重算重写、agent 改了文件 DB 永不知情。
        现由 DbBackend 按需从 DB 渲染成只读虚拟文件，投影与落盘一同退役（Phase 3.1）。
        """
        try:
            await self.user_repo.upsert(user_id, payload)
            await self.db.commit()
        except Exception as e:
            # L2 是唯一真理源，写失败 = 数据丢失，必须是 error 而不是 warning
            logger.error(
                "write_user_memory_db_failed",
                user_id=str(user_id),
                error=str(e),
            )
            raise

    async def get_user_memory(self, user_id: UUID) -> Optional[UserMemory]:
        """从 DB 读用户长期记忆"""
        return await self.user_repo.get(user_id)

    async def merge_user_updates(self, current: UserMemory, updates: dict) -> UserMemory:
        """粗粒度 merge：list 字段 append，其他 set。

        ⚠️ 无来源仲裁，仅适用于单一写入方场景；L2 多写入方请用 merge_with_source。
        """
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

    async def merge_with_source(
        self,
        current: UserMemory,
        updates: dict,
        source: Literal["user", "agent", "resume"],
    ) -> UserMemory:
        """带来源仲裁的 L2 合并（agent-context-overhaul Phase 3.3）。

        L2 从"业务代码主导写"改为"业务代码 + agent 都可写"后，必须防止
        简历重解析整体抹掉用户在对话里积累的偏好。

        规则（见 design.md「写入仲裁」）：
        - 优先级 **user > agent > resume**；低优先级写入遇到更高优先级来源
          的字段 → 跳过该字段并 log，不覆盖
        - **resume 只填空**：字段已有来源且不是 resume 时不写入；
          列表字段也不用 append 去扩写用户已确认的清单
        - 列表字段：同优先级（或首次写入）append 去重，便于对话中逐步累加；
          **更高优先级来源整体覆盖**，否则用户无法清除 agent 积累错的值
        - 写成功后记录字段来源，供下一轮仲裁使用

        Args:
            current: 当前 UserMemory
            updates: 待写字段，形状同 merge_user_updates（如
                {"long_term_preferences": {"locations": ["上海"]}, "career_direction": "..."}）
            source: 本次写入方

        Returns:
            仲裁后的新 UserMemory（不就地修改入参）
        """
        incoming_rank = PREFERENCE_SOURCE_PRIORITY.get(source, 0)
        data = current.model_dump()
        sources = dict(current.preference_sources)
        prefs_data = data.get("long_term_preferences") or {}
        skipped: list[str] = []

        def owned_elsewhere(key: str) -> bool:
            """该字段是否已被更高优先级来源占用"""
            owner = sources.get(key)
            if not owner:
                return False
            if PREFERENCE_SOURCE_PRIORITY.get(owner, 0) > incoming_rank:
                return True
            # resume 只填空：只要字段已有其他来源，就不再写
            return source == "resume" and owner != "resume"

        def owner_rank(key: str) -> int:
            return PREFERENCE_SOURCE_PRIORITY.get(sources.get(key) or "", 0)

        def merge_list(old: list, new: list, key: str) -> list:
            """严格更高优先级来源 → 整体覆盖；其余情况 → append 去重"""
            if incoming_rank > owner_rank(key):
                return list(new)
            combined = list(old)
            for item in new:
                if item not in combined:
                    combined.append(item)
            return combined

        pref_updates = updates.get("long_term_preferences") or {}
        for key, value in pref_updates.items():
            if key not in prefs_data and not hasattr(JobPreference, key):
                continue
            if owned_elsewhere(key):
                skipped.append(key)
                continue
            old = prefs_data.get(key)
            if isinstance(old, list) and isinstance(value, list):
                if source == "resume" and old:
                    # 简历不扩写已有列表
                    skipped.append(key)
                    continue
                prefs_data[key] = merge_list(old, value, key)
            elif value is not None:
                prefs_data[key] = value
            sources[key] = source

        # 顶层字段（career_direction / negative_signals 等）同样参与仲裁
        for key, value in updates.items():
            if key == "long_term_preferences" or key not in data:
                continue
            if owned_elsewhere(key):
                skipped.append(key)
                continue
            old = data.get(key)
            if isinstance(old, list) and isinstance(value, list):
                data[key] = merge_list(old, value, key)
            elif value is not None:
                data[key] = value
            sources[key] = source

        data["long_term_preferences"] = prefs_data
        data["preference_sources"] = sources

        if skipped:
            logger.info(
                "user_memory_write_arbitrated",
                source=source,
                skipped_fields=skipped,
            )
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
        self,
        current: SessionMemory,
        updates: dict,
        mode: Literal["merge", "replace"] = "merge",
    ) -> SessionMemory:
        """粗粒度 merge：list 字段 append，标量字段 set，JobPreference 嵌套 merge。

        Args:
            current: 当前 SessionMemory
            updates: 要更新的字段
            mode: "merge"（默认，append 去重）或 "replace"（覆盖 pref list 字段）。
                  open_questions / recent_decisions 不受 mode 影响，始终 append。
        """
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
                        if mode == "replace":
                            prefs_data[pk] = pv
                        else:
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
                # open_questions / recent_decisions 不受 mode 影响，始终 append
                old = data.get(key, [])
                combined = list(old)
                for item in value:
                    if item not in combined:
                        combined.append(item)
                data[key] = combined
            elif key in data and value is not None:
                data[key] = value

        return SessionMemory(**data)
