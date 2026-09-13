"""LangGraph checkpointer 生命周期管理（agent-context-overhaul Phase 1.1）。

为什么需要独立模块：
- `AsyncPostgresSaver` 需要 **psycopg 3**，而 SQLAlchemy 侧用的是 asyncpg，
  两者驱动与连接串格式都不兼容（`DATABASE_URL` 带 `postgresql+asyncpg://`
  方言前缀，直接喂给 saver 会报错），因此这里走 `settings.CHECKPOINTER_DSN`
  的独立 DSN + 独立连接池，只复用同一个 RDS 实例。
- saver 必须是**进程级单例**：连接池与 checkpoint 表句柄不能每轮重建。

失败策略（见 design.md「失败与降级」）：初始化失败即向上抛出，
让应用启动失败（fail fast）——静默降级会退回"每轮失忆"且极难排查。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import get_settings
from app.utils.logger import get_logger

if TYPE_CHECKING:  # 仅类型标注；运行时导入在 init 内做，避免开关关闭时强依赖
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

logger = get_logger()

_saver: "AsyncPostgresSaver | None" = None
_pool: "AsyncConnectionPool | None" = None


async def init_checkpointer() -> None:
    """创建全局 saver 并确保 checkpoint 表存在（在 FastAPI lifespan 中调用）。

    - 开关 ENABLE_AGENT_CHECKPOINTER=False 时直接返回，get_checkpointer() 得 None，
      agent 退回"每轮全量重建历史"的旧路径（回滚用）
    - psycopg 连接参数按 langgraph 官方要求：autocommit=True + prepare_threshold=0
    """
    global _saver, _pool

    settings = get_settings()
    if not settings.ENABLE_AGENT_CHECKPOINTER:
        logger.info("agent_checkpointer_disabled")
        return

    # 运行时导入：开关关闭的部署无需安装 psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    pool: AsyncConnectionPool = AsyncConnectionPool(
        conninfo=settings.CHECKPOINTER_DSN,
        min_size=1,
        max_size=settings.CHECKPOINT_POOL_MAX_SIZE,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    try:
        await pool.open(wait=True)
        saver = AsyncPostgresSaver(pool)
        # 幂等建表（首次启动创建 checkpoint 系列表）
        await saver.setup()
    except Exception:
        # 半成品池必须回收，否则连接泄漏 + 错误被掩盖
        await pool.close()
        logger.error("agent_checkpointer_init_failed")
        raise

    _pool = pool
    _saver = saver
    logger.info(
        "agent_checkpointer_ready",
        host=settings.RDS_HOST,
        port=settings.RDS_PORT,
        pool_max_size=settings.CHECKPOINT_POOL_MAX_SIZE,
    )


def get_checkpointer() -> "AsyncPostgresSaver | None":
    """返回全局 saver；未启用或未初始化时为 None（调用方据此走回滚分支）"""
    return _saver


async def close_checkpointer() -> None:
    """关闭连接池（在 lifespan 退出时调用）"""
    global _saver, _pool

    if _pool is not None:
        await _pool.close()
        logger.info("agent_checkpointer_closed")
    _saver = None
    _pool = None
