"""
PostgreSQL Checkpointer for LangGraph
持久化 Agent 状态到 PostgreSQL 数据库
"""
import json
import uuid
from typing import Any, Optional, Sequence
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class PostgresCheckpointer(BaseCheckpointSaver):
    """
    PostgreSQL-based checkpoint saver for LangGraph
    
    Stores checkpoints in a PostgreSQL database table.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
    
    async def aget_tuple(self, thread_id: str) -> Optional[CheckpointTuple]:
        """Get checkpoint tuple by thread_id"""
        query = text("""
            SELECT thread_id, checkpoint, metadata, parent_checkpoint
            FROM langgraph_checkpoints
            WHERE thread_id = :thread_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = await self.session.execute(query, {"thread_id": thread_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        thread_id, checkpoint_json, metadata_json, parent_checkpoint = row
        
        checkpoint = json.loads(checkpoint_json)
        metadata = json.loads(metadata_json) if metadata_json else {}
        
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config={"configurable": {"thread_id": parent_checkpoint}} if parent_checkpoint else None,
        )
    
    async def alist(
        self,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Sequence[CheckpointTuple]:
        """List checkpoints"""
        # Simplified implementation - can be enhanced with filtering
        query = text("""
            SELECT thread_id, checkpoint, metadata, parent_checkpoint
            FROM langgraph_checkpoints
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        result = await self.session.execute(query, {"limit": limit or 100})
        rows = result.fetchall()
        
        tuples = []
        for row in rows:
            thread_id, checkpoint_json, metadata_json, parent_checkpoint = row
            checkpoint = json.loads(checkpoint_json)
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            tuples.append(CheckpointTuple(
                config={"configurable": {"thread_id": thread_id}},
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config={"configurable": {"thread_id": parent_checkpoint}} if parent_checkpoint else None,
            ))
        
        return tuples
    
    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, int | float | str],
    ) -> dict[str, Any]:
        """Save checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        
        query = text("""
            INSERT INTO langgraph_checkpoints (
                thread_id, checkpoint, metadata, parent_checkpoint, created_at
            ) VALUES (
                :thread_id, 
                :checkpoint::jsonb, 
                :metadata::jsonb, 
                :parent_checkpoint,
                NOW()
            )
            ON CONFLICT (thread_id) 
            DO UPDATE SET 
                checkpoint = EXCLUDED.checkpoint,
                metadata = EXCLUDED.metadata,
                parent_checkpoint = EXCLUDED.parent_checkpoint,
                created_at = NOW()
        """)
        
        parent_checkpoint = metadata.get("step", 0) > 0 and config["configurable"].get("thread_id")
        
        await self.session.execute(query, {
            "thread_id": thread_id,
            "checkpoint": json.dumps(checkpoint),
            "metadata": json.dumps(metadata),
            "parent_checkpoint": parent_checkpoint,
        })
        
        return config
    
    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save writes (not implemented for basic checkpointing)"""
        pass
