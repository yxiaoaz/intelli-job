"""Session Intent Repository - 数据访问层"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.session_intent import SessionIntent
import uuid
from typing import Optional


class SessionIntentRepository:
    """Session Intent 数据访问层
    
    提供对 session_intents 表的 CRUD 操作，
    支持智能合并策略。
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_thread_id(
        self, 
        thread_id: str, 
        user_id: uuid.UUID
    ) -> Optional[SessionIntent]:
        """获取 session 的意图
        
        Args:
            thread_id: LangGraph thread ID
            user_id: 用户 ID
            
        Returns:
            SessionIntent 对象或 None
        """
        result = await self.db.execute(
            select(SessionIntent).where(
                SessionIntent.thread_id == thread_id,
                SessionIntent.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    
    async def upsert_by_thread_id(
        self,
        thread_id: str,
        user_id: uuid.UUID,
        updates: dict
    ) -> SessionIntent:
        """Upsert session intent（智能合并）
        
        Args:
            thread_id: LangGraph thread ID
            user_id: 用户 ID
            updates: LLM 提取的 IntentExtractionResult.dict()
                     注意：LLM 返回的是完整列表，不是增量
        
        Returns:
            更新或创建后的 SessionIntent 对象
        """
        # 查询现有记录
        existing = await self.get_by_thread_id(thread_id, user_id)
        
        if existing:
            # 智能合并策略
            merged = self._smart_merge(existing, updates)
            
            # 更新字段
            for key, value in merged.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # 创建新记录
            new_intent = SessionIntent(
                thread_id=thread_id,
                user_id=user_id,
                **updates
            )
            self.db.add(new_intent)
            await self.db.commit()
            await self.db.refresh(new_intent)
            return new_intent
    
    async def get_by_user_id(
        self, 
        user_id: uuid.UUID
    ) -> list[SessionIntent]:
        """获取用户所有 session 的意图
        
        Args:
            user_id: 用户 ID
            
        Returns:
            SessionIntent 列表
        """
        result = await self.db.execute(
            select(SessionIntent)
            .where(SessionIntent.user_id == user_id)
            .order_by(SessionIntent.last_updated_at.desc())
        )
        return result.scalars().all()
    
    def _smart_merge(
        self, 
        existing: SessionIntent, 
        updates: dict
    ) -> dict:
        """智能合并策略
        
        关键逻辑：
        - 如果 updates 中某个字段为 null → 不更新（保持原值）
        - 如果 updates 中某个字段为非空列表 → **直接替换**（LLM 已处理追加/替换逻辑）
        - 如果 updates 中某个字段为标量 → 直接替换
        
        为什么直接替换？
        因为 LLM 在 extract_intent 时已经根据用户语义判断了是追加还是替换，
        返回的已经是最终结果，不需要再合并。
        
        Args:
            existing: 现有的 SessionIntent 对象
            updates: LLM 提取的更新字典
            
        Returns:
            合并后的字典（只包含需要更新的字段）
        """
        merged = {}
        
        for key, new_value in updates.items():
            if new_value is None:
                # LLM 未提及该字段，保持原值
                continue
            
            old_value = getattr(existing, key, None)
            
            if isinstance(new_value, list):
                # 列表字段：直接替换（LLM 已处理好）
                merged[key] = new_value
            else:
                # 标量字段：直接替换
                merged[key] = new_value
        
        return merged
