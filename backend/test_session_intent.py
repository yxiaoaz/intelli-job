"""测试 SessionIntent 功能"""

import asyncio
from sqlalchemy import inspect, text
from app.database import AsyncSessionLocal
from app.models.session_intent import SessionIntent
from app.repositories.session_intent_repo import SessionIntentRepository
import uuid


async def test_session_intent():
    """测试 SessionIntent 模型和 Repository"""
    
    print("=" * 60)
    print("测试 SessionIntent 功能")
    print("=" * 60)
    
    # 1. 检查表是否存在
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name='session_intents'"
        ))
        tables = result.fetchall()
        
        if tables:
            print("\n✅ session_intents 表存在")
            
            # 获取列信息
            columns_result = await db.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='session_intents' ORDER BY ordinal_position"
            ))
            columns = columns_result.fetchall()
            
            print("\n表结构:")
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")
        else:
            print("\n❌ session_intents 表不存在")
            return
    
    # 2. 测试 Repository CRUD
    print("\n" + "=" * 60)
    print("测试 Repository CRUD")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        repo = SessionIntentRepository(db)
        
        # 创建测试用户
        from app.models import User
        test_user = User(
            id=uuid.uuid4(),
            email=f"test-{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="dummy_hash"
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        
        test_user_id = test_user.id
        test_thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
        
        print(f"\n测试用户ID: {test_user_id}")
        print(f"测试会话ID: {test_thread_id}")
        
        # Test 1: 创建新的 SessionIntent
        print("\n[Test 1] 创建新的 SessionIntent...")
        intent_data = {
            "preferred_city": ["北京", "上海"],
            "preferred_job_titles": ["产品经理", "运营"],
            "salary_expectation": {"min": 15000, "max": 25000, "currency": "CNY"},
            "skills": ["Python", "数据分析"],
            "search_direction": "互联网"
        }
        
        new_intent = await repo.upsert_by_thread_id(
            thread_id=test_thread_id,
            user_id=test_user_id,
            updates=intent_data
        )
        
        print(f"✅ 创建成功: ID={new_intent.id}")
        print(f"   城市: {new_intent.preferred_city}")
        print(f"   岗位: {new_intent.preferred_job_titles}")
        
        # Test 2: 读取 SessionIntent
        print("\n[Test 2] 读取 SessionIntent...")
        read_intent = await repo.get_by_thread_id(test_thread_id, test_user_id)
        
        if read_intent:
            print(f"✅ 读取成功")
            print(f"   城市: {read_intent.preferred_city}")
            print(f"   岗位: {read_intent.preferred_job_titles}")
        else:
            print("❌ 读取失败")
        
        # Test 3: 更新 SessionIntent（智能合并）
        print("\n[Test 3] 更新 SessionIntent（替换场景）...")
        update_data = {
            "preferred_city": ["深圳"]  # 替换：从["北京", "上海"]变为["深圳"]
        }
        
        updated_intent = await repo.upsert_by_thread_id(
            thread_id=test_thread_id,
            user_id=test_user_id,
            updates=update_data
        )
        
        print(f"✅ 更新成功")
        print(f"   城市: {updated_intent.preferred_city} (应该是 ['深圳'])")
        print(f"   岗位: {updated_intent.preferred_job_titles} (保持不变)")
        
        # Test 4: 验证智能合并
        if updated_intent.preferred_city == ["深圳"]:
            print("✅ 智能合并测试通过：城市被正确替换")
        else:
            print(f"❌ 智能合并测试失败：期望 ['深圳']，实际 {updated_intent.preferred_city}")
        
        # Test 5: 删除测试数据（清理）
        print("\n[Test 5] 清理测试数据...")
        await db.delete(updated_intent)
        await db.delete(test_user)  # 删除测试用户
        await db.commit()
        print("✅ 测试数据已清理")
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_session_intent())
