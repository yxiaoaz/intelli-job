"""数据库虚拟文件后端（agent-context-overhaul Phase 2.1）。

把 `resumes` / `user_memories` 两张表按路径实时渲染成只读虚拟文件，经
`CompositeBackend` 挂到 `/resume/` 与 `/memory/` 两条路由下：

    /resume/active.md   ← 当前启用简历（extracted_content 渲染）
    /memory/profile.md  ← 长期画像（UserMemory 渲染）

三条硬约束：
1. **严格只读**。写操作返回指引性错误（告诉 agent 改用哪个工具），
   否则它会反复重试（见 design.md D7）
2. **所有查询强制按 user_id 过滤**，防越权
3. **无数据 / 查询异常都返回文本，不抛异常**——抛了会中断 agent 循环
   （design.md「失败与降级」）

路径形态注意：`CompositeBackend._route_for_path` 会**剥掉路由前缀**再转发，
所以运行期真实收到的是 `/active.md`、`/profile.md`；同时兼容未剥前缀的
完整形式（单测直接调 DbBackend 时用 `/resume/active.md`）。
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    GlobResult,
    LsResult,
    ReadResult,
    WriteResult,
)

from app.core.backends.renderers import render_resume_markdown
from app.memory.markdown_renderer import render_user_memory
from app.memory.schemas import UserMemory
from app.utils.logger import get_logger

logger = get_logger()

# 只读错误文案必须指明替代工具，否则 agent 会反复重试（D7）
READONLY_ERROR = (
    "`/resume/` 与 `/memory/` 是由数据库实时渲染的只读视图，无法写入。"
    "更新长期偏好请用 `update_user_memory` 工具；"
    "更新当前会话状态请用 `update_session_memory` 工具。"
)

NO_RESUME_TEXT = (
    "（未上传简历）请先在简历页上传简历，或引导用户去上传。"
    "注意：无简历时无法评估匹配度，不要凭空给出匹配分数。"
)
NO_PARSED_TEXT = "（简历已上传但尚未解析成功，暂无内容可读）"
DB_ERROR_TEXT = "（简历/记忆信息暂时不可用，请稍后重试；不要因此中断回复用户）"

# 渲染结果进程内缓存上限（key = resume_id + 更新时间，切换简历自然失效）
_RESUME_CACHE_MAX = 128
_resume_render_cache: dict[str, tuple[str, str]] = {}


def _canonical(file_path: str) -> str:
    """归一化路径：CompositeBackend 会剥掉路由前缀，这里把两种形态统一"""
    normalized = (file_path or "").strip()
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return {
        "/resume/active.md": "/active.md",
        "/memory/profile.md": "/profile.md",
    }.get(normalized, normalized)


class DbBackend(BackendProtocol):
    """只读虚拟文件后端：从数据库渲染 /resume/active.md 与 /memory/profile.md。"""

    def __init__(
        self,
        user_id: str | uuid.UUID,
        session_factory: Callable[..., Any],
        base_dir: str,
    ) -> None:
        # 构造时固定 user_id，所有查询都带上它，杜绝跨用户读取
        self._user_id = uuid.UUID(str(user_id))
        self._session_factory = session_factory
        # MemoryService 目前仍要求 base_dir（Phase 3.1 去掉落盘后可一并移掉）
        self._base_dir = base_dir

    # ── 读 ──────────────────────────────────────────────────────────────

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        key = _canonical(file_path)
        try:
            if key == "/active.md":
                content = await self._read_active_resume()
            elif key == "/profile.md":
                content = await self._read_profile()
            else:
                return ReadResult(
                    error=(
                        f"文件不存在: {file_path}。"
                        "可用路径：/resume/active.md、/memory/profile.md"
                    )
                )
        except Exception as e:  # 不中断 agent 循环（design.md「失败与降级」）
            logger.error(
                "db_backend_read_failed",
                user_id=str(self._user_id),
                path=file_path,
                error=str(e),
            )
            content = DB_ERROR_TEXT

        return ReadResult(file_data={"content": content, "encoding": "utf-8"})

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        """同步入口：本后端只有异步数据源，不提供同步读取。

        deepagents 的工具链走 async 路径（aread），此方法仅为满足协议存在。
        """
        return ReadResult(
            error="DbBackend 仅支持异步读取（aread）：数据源是 Postgres 异步会话"
        )

    async def als(self, path: str) -> LsResult:
        key = _canonical(path)
        entries: list[dict[str, Any]] = []
        if key in ("/", "", "/resume", "/resume/", "/memory", "/memory/"):
            if key in ("/", "", "/resume", "/resume/"):
                entries.append({"path": "/resume/active.md"})
            if key in ("/", "", "/memory", "/memory/"):
                entries.append({"path": "/memory/profile.md"})
        return LsResult(entries=entries)

    async def aglob(self, pattern: str, path: str = "/") -> GlobResult:
        from fnmatch import fnmatch

        known = ["/resume/active.md", "/memory/profile.md"]
        return GlobResult(
            matches=[{"path": p} for p in known if fnmatch(p, pattern)]
        )

    # ── 写：一律拒绝并给出替代工具指引（D7）────────────────────────────

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        logger.info(
            "db_backend_write_denied",
            user_id=str(self._user_id),
            path=file_path,
        )
        return WriteResult(error=READONLY_ERROR)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,  # noqa: FBT001, FBT002
    ) -> EditResult:
        logger.info(
            "db_backend_write_denied",
            user_id=str(self._user_id),
            path=file_path,
        )
        return EditResult(error=READONLY_ERROR)

    def write(self, file_path: str, content: str) -> WriteResult:
        return WriteResult(error=READONLY_ERROR)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,  # noqa: FBT001, FBT002
    ) -> EditResult:
        return EditResult(error=READONLY_ERROR)

    # ── 数据源 ──────────────────────────────────────────────────────────

    async def _read_active_resume(self) -> str:
        from sqlalchemy import select

        from app.models import Resume

        async with self._session_factory() as session:
            result = await session.execute(
                select(Resume)
                .where(
                    Resume.user_id == self._user_id,
                    Resume.active_status.is_(True),
                )
                .order_by(Resume.parsed_at.desc())
            )
            resume = result.scalars().first()

        if not resume:
            return NO_RESUME_TEXT
        if not resume.extracted_content:
            return NO_PARSED_TEXT

        signature = f"{resume.updated_at or resume.parsed_at or ''}"
        cache_key = str(resume.id)
        cached = _resume_render_cache.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1]

        markdown = render_resume_markdown(resume.extracted_content)
        if len(_resume_render_cache) >= _RESUME_CACHE_MAX:
            _resume_render_cache.clear()
        _resume_render_cache[cache_key] = (signature, markdown)
        return markdown

    async def _read_profile(self) -> str:
        from app.memory.service import MemoryService

        async with self._session_factory() as session:
            service = MemoryService(session, base_dir=self._base_dir)
            memory = await service.get_user_memory(self._user_id)

        # 无记录也要出骨架：agent 需要知道"哪些字段还是空的"才能问对问题
        return render_user_memory(memory or UserMemory())
