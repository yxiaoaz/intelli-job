"""Run this script once to create the job_ai_explanations table."""
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    sql = """
    CREATE TABLE IF NOT EXISTS job_ai_explanations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        job_id UUID NOT NULL REFERENCES job_items(id) ON DELETE CASCADE,
        match_score INTEGER,
        match_reasons JSONB,
        match_risks JSONB,
        resume_tips JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, job_id)
    );
    """
    async with engine.begin() as conn:
        await conn.execute(text(sql))
    print("Table job_ai_explanations created successfully.")


if __name__ == "__main__":
    asyncio.run(migrate())
