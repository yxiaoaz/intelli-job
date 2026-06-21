"""
Database migration: Add security_question and security_answer_hash columns to users table
Run this script after updating the User model.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings


async def migrate():
    settings = get_settings()
    
    # Create engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    try:
        async with engine.begin() as conn:
            # Check if columns already exist
            result = await conn.execute(
                text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('security_question', 'security_answer_hash')
                """)
            )
            existing_columns = [row[0] for row in result.fetchall()]
            
            if 'security_question' not in existing_columns:
                print("Adding security_question column...")
                await conn.execute(
                    text("""
                    ALTER TABLE users 
                    ADD COLUMN security_question VARCHAR(256)
                    """)
                )
                print("✓ security_question column added")
            else:
                print("✓ security_question column already exists")
            
            if 'security_answer_hash' not in existing_columns:
                print("Adding security_answer_hash column...")
                await conn.execute(
                    text("""
                    ALTER TABLE users 
                    ADD COLUMN security_answer_hash VARCHAR(256)
                    """)
                )
                print("✓ security_answer_hash column added")
            else:
                print("✓ security_answer_hash column already exists")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("Running database migration: Add security question fields...\n")
    asyncio.run(migrate())
