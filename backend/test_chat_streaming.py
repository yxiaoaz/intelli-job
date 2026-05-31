"""
测试多轮对话和流式输出功能
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from app.core.agents.conversation_agent import ConversationAgent
from app.utils.logger import setup_logging, get_logger

load_dotenv()


async def test_streaming():
    """测试流式输出"""
    logger = get_logger()
    
    # 创建 Agent（不带 checkpointer，用于测试）
    agent = ConversationAgent()
    
    session_id = "test-session-001"
    
    print("=" * 60)
    print("测试流式输出")
    print("=" * 60)
    
    # 第一轮对话
    print("\n📝 用户: 帮我找北京的产品经理职位\n")
    print("🤖 AI: ", end="", flush=True)
    
    async for event in agent.chat_stream(
        message="帮我找北京的产品经理职位",
        session_id=session_id
    ):
        if event["type"] == "token":
            print(event["data"], end="", flush=True)
        elif event["type"] == "tool_start":
            print(f"\n[工具开始: {event['data']['tool']}]", end="", flush=True)
        elif event["type"] == "tool_end":
            print(f"\n[工具完成: {event['data']['tool']}]", end="", flush=True)
        elif event["type"] == "final_response":
            print("\n✅ 回复完成")
        elif event["type"] == "error":
            print(f"\n❌ 错误: {event['data']}")
    
    print("\n" + "=" * 60)
    
    # 第二轮对话（测试上下文）
    print("\n📝 用户: 这些职位的薪资怎么样？\n")
    print("🤖 AI: ", end="", flush=True)
    
    async for event in agent.chat_stream(
        message="这些职位的薪资怎么样？",
        session_id=session_id  # 使用相同的 session_id
    ):
        if event["type"] == "token":
            print(event["data"], end="", flush=True)
        elif event["type"] == "final_response":
            print("\n✅ 回复完成")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(test_streaming())
