"""
Conversation Agent Tests

Tests for:
- Chat endpoint
- Message history
- AI responses
"""
import json

import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


class FailingChatAgent:
    """chat_stream 抛异常的 Agent 替身（模拟 LLM 链路故障）"""

    def __init__(self, fail_after_token: bool = True):
        self._fail_after_token = fail_after_token

    async def chat_stream(self, **kwargs):
        if self._fail_after_token:
            yield {"type": "token", "data": "部分回复"}
        raise RuntimeError("LLM down")


class TestChatEndpoint:
    """Test chat conversation endpoint"""
    
    @pytest.mark.asyncio
    async def test_send_message(self, authenticated_client):
        """Test sending a message to the AI assistant"""
        # First create a session
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        assert session_response.status_code == 200
        session_id = session_response.json()["id"]
        
        # Send a message
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "帮我找一些产品经理的工作"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "reply" in data
        assert len(data["reply"]) > 0
    
    @pytest.mark.asyncio
    async def test_chat_without_auth(self, client):
        """Test chat without authentication"""
        # Try to create session without auth
        response = await client.post("/api/v1/chat/sessions")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_conversation_context(self, authenticated_client):
        """Test that conversation maintains context"""
        # Create session
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        # First message
        response1 = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "我想找北京的工作"}
        )
        assert response1.status_code == 200
        
        # Second message (should understand context)
        response2 = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "薪资怎么样？"}
        )
        assert response2.status_code == 200


class TestMessageHistory:
    """Test message history endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_message_history(self, authenticated_client):
        """Test getting conversation history"""
        # Get sessions (serves as history)
        response = await authenticated_client.get("/api/v1/chat/sessions")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_clear_message_history(self, authenticated_client):
        """Test clearing conversation history"""
        # Endpoint may not be implemented yet
        pass


class TestJobSearchViaChat:
    """Test job search through chat interface"""
    
    @pytest.mark.asyncio
    async def test_search_jobs_in_chat(self, authenticated_client):
        """Test searching jobs via chat command"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "搜索上海的数据分析师职位"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should contain job recommendations or search results
        assert "reply" in data
    
    @pytest.mark.asyncio
    async def test_filter_jobs_in_chat(self, authenticated_client):
        """Test filtering jobs via chat"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "只看互联网行业的职位"
            }
        )
        
        assert response.status_code == 200


class TestResumeAnalysisViaChat:
    """Test resume analysis through chat"""
    
    @pytest.mark.asyncio
    async def test_analyze_resume(self, authenticated_client):
        """Test requesting resume analysis via chat"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "分析我的简历"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "reply" in data
    
    @pytest.mark.asyncio
    async def test_resume_improvement_suggestions(self, authenticated_client):
        """Test getting resume improvement suggestions"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "如何改进我的简历？"
            }
        )
        
        assert response.status_code == 200


class TestChatStreaming:
    """Test streaming chat responses"""

    @pytest.mark.asyncio
    async def test_streaming_response(self, authenticated_client):
        """Test streaming chat response"""
        # Note: Streaming endpoint may not be implemented yet
        # This is a placeholder for future implementation
        pass


class TestChatStreamDegradation:
    """Agent 流式链路异常时的降级行为：发降级 content 帧而非裸 error 帧"""

    @pytest.mark.asyncio
    async def test_agent_exception_sends_degraded_frames(self, authenticated_client, test_engine):
        """Agent 抛异常 → SSE 收到降级 token 帧 + final_response 帧，而非 error 帧"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]

        # 持久化走 AsyncSessionLocal（不经过 get_db 依赖），需指向测试引擎
        test_session_maker = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

        with patch("app.api.v1.chat.conversation_agent", FailingChatAgent()), \
                patch("app.api.v1.chat.AsyncSessionLocal", test_session_maker):
            response = await authenticated_client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                json={"message": "你好"},
            )

        assert response.status_code == 200
        events = [
            json.loads(line[len("data: "):])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        event_types = [e["type"] for e in events]

        assert "error" not in event_types
        assert "token" in event_types
        assert "final_response" in event_types

        degraded_token = next(e for e in events if e["type"] == "token" and "暂时不可用" in e["data"])
        assert "职位搜索" in degraded_token["data"]
        final_event = next(e for e in events if e["type"] == "final_response")
        assert "暂时不可用" in final_event["data"]

    @pytest.mark.asyncio
    async def test_degraded_message_persisted(self, authenticated_client, test_engine):
        """降级消息已持久化到会话历史（走部分回复持久化逻辑）"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]

        test_session_maker = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

        with patch("app.api.v1.chat.conversation_agent", FailingChatAgent(fail_after_token=False)), \
                patch("app.api.v1.chat.AsyncSessionLocal", test_session_maker):
            response = await authenticated_client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                json={"message": "你好"},
            )

        assert response.status_code == 200

        messages_response = await authenticated_client.get(
            f"/api/v1/chat/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()

        roles = {m["role"]: m["content"] for m in messages}
        assert roles.get("user") == "你好"
        assert "暂时不可用" in roles.get("assistant", "")


class _FakeChunk:
    """astream_events chunk 替身（只用到 content 属性）"""

    def __init__(self, content: str):
        self.content = content


class _DupStreamDeepAgent:
    """模拟 deepagents 链路下的事件双发 + 内部 LLM 流泄露：

    每个 token 双发 on_chat_model_stream（内层 name=ChatOpenAI /
    外层 name=FallbackChatModel，run_id 相同），并在工具阶段
    穿插一条 QueryFormulator 内部流的 token（name=ChatOpenAI）。
    """

    async def astream_events(self, messages, config=None, version="v2"):
        for tok in ("你好", "，", "世界"):
            yield {
                "event": "on_chat_model_stream",
                "name": "ChatOpenAI",
                "data": {"chunk": _FakeChunk(tok)},
            }
            yield {
                "event": "on_chat_model_stream",
                "name": "FallbackChatModel",
                "data": {"chunk": _FakeChunk(tok)},
            }
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "data": {"chunk": _FakeChunk('{"expanded_query": "泄露"}')},
        }


class TestChatStreamDedup:
    """deepagents 链路下 on_chat_model_stream 双发的去重过滤"""

    @pytest.mark.asyncio
    async def test_stream_dedupes_duplicate_model_events(self, monkeypatch):
        """双发/内部流 token 只保留外层事件，final_response 无重复文本"""
        from app.core.agents.conversation_agent import ConversationAgent

        # __new__ 跳过 __init__，避免依赖真实 LLM 供应商配置
        agent = ConversationAgent.__new__(ConversationAgent)
        agent._stream_source_name = "FallbackChatModel"

        async def fake_prepare(message, session_id, user_id=None):
            return (
                _DupStreamDeepAgent(),
                {"configurable": {"thread_id": session_id}},
                [{"role": "user", "content": message}],
            )

        monkeypatch.setattr(agent, "_prepare_messages", fake_prepare)

        events = []
        async for event in agent.chat_stream(message="hi", session_id="s1"):
            events.append(event)

        tokens = [e["data"] for e in events if e["type"] == "token"]
        assert tokens == ["你好", "，", "世界"]

        final = next(e for e in events if e["type"] == "final_response")
        assert final["data"] == "你好，世界"
        assert "expanded_query" not in final["data"]


class TestAgentTools:
    """Test agent tool invocations"""
    
    @pytest.mark.asyncio
    async def test_agent_can_search_jobs(self, authenticated_client):
        """Test that agent can invoke job search tool"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "帮我找5个北京的Java开发工作"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should mention job search results
        reply = data.get("reply", "")
        assert len(reply) > 0
    
    @pytest.mark.asyncio
    async def test_agent_can_bookmark_jobs(self, authenticated_client):
        """Test that agent can help bookmark jobs"""
        session_response = await authenticated_client.post("/api/v1/chat/sessions")
        session_id = session_response.json()["id"]
        
        response = await authenticated_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "message": "收藏这个职位"
            }
        )
        
        assert response.status_code == 200


class _FakeToolEventAgent:
    """astream_events 替身：按顺序吐出预置的工具事件（含 run_id 配对信息）"""

    def __init__(self, events):
        self._events = events

    async def astream_events(self, messages, config=None, version="v2"):
        for ev in self._events:
            yield ev


def _tool_start(name, run_id, args=None):
    return {
        "event": "on_tool_start", "name": name, "run_id": run_id,
        "data": {"input": args if args is not None else {}},
    }


def _tool_end(name, run_id, output):
    return {
        "event": "on_tool_end", "name": name, "run_id": run_id,
        "data": {"output": output},
    }


def _tool_error(name, run_id, error):
    return {
        "event": "on_tool_error", "name": name, "run_id": run_id,
        "data": {"error": error},
    }


def _make_agent(monkeypatch, events):
    """跳过 __init__（避免依赖真实 LLM 供应商配置），接入 _FakeToolEventAgent"""
    from app.core.agents.conversation_agent import ConversationAgent

    agent = ConversationAgent.__new__(ConversationAgent)
    agent._stream_source_name = "FallbackChatModel"

    fake_inner_agent = _FakeToolEventAgent(events)

    async def fake_prepare(message, session_id, user_id=None):
        return fake_inner_agent, {"configurable": {"thread_id": session_id}}, []

    monkeypatch.setattr(agent, "_prepare_messages", fake_prepare)
    return agent


async def _collect(agent):
    out = []
    async for ev in agent.chat_stream(message="hi", session_id="s1"):
        out.append(ev)
    return out


class TestToolEventsPairing:
    """ui-redesign Phase 2.4：tool_start/tool_end 结构化逐对事件的完整性"""

    @pytest.mark.asyncio
    async def test_start_end_pairs_by_run_id(self, monkeypatch):
        """start/end 按 run_id 严格配对：id/ts/duration_ms/result_summary 齐全"""
        events = [
            _tool_start("search_jobs", "r-1", {"location": "北京", "role": "算法实习生"}),
            _tool_end("search_jobs", "r-1", json.dumps({"type": "job_search_results", "jobs": [{}, {}, {}]})),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        starts = [e for e in collected if e["type"] == "tool_start"]
        ends = [e for e in collected if e["type"] == "tool_end"]
        assert len(starts) == 1 and len(ends) == 1
        assert starts[0]["data"]["id"] == ends[0]["data"]["id"] == "tc_001"
        assert starts[0]["data"]["args"] == {"location": "北京", "role": "算法实习生"}
        assert "ts" in starts[0]["data"]
        assert ends[0]["data"]["status"] == "ok"
        assert ends[0]["data"]["result_summary"] == "找到 3 个岗位"
        assert ends[0]["data"]["duration_ms"] >= 0
        # 旧字段事件仍在（过渡版本兼容）
        assert any(e["type"] == "tool_calls" for e in collected)
        assert any(e["type"] == "tool_results" for e in collected)
        tool_events = next(e for e in collected if e["type"] == "tool_events")
        assert tool_events["data"][0]["args_summary"] == "北京 · 算法实习生"

    @pytest.mark.asyncio
    async def test_orphan_end_is_ignored(self, monkeypatch):
        """孤儿 end（找不到配对 start）：不发 tool_end，也不进 tool_results 批量事件"""
        events = [
            _tool_end("search_jobs", "r-unknown", "{}"),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        assert not any(e["type"] == "tool_end" for e in collected)
        assert not any(e["type"] == "tool_results" for e in collected)
        assert not any(e["type"] == "tool_events" for e in collected)

    @pytest.mark.asyncio
    async def test_ids_unique_within_turn_for_repeated_calls(self, monkeypatch):
        """同轮内多次同名调用：id 不重复，各自按 run_id 正确配对"""
        events = [
            _tool_start("read_file", "r-1", {"file_path": "profile.md"}),
            _tool_start("read_file", "r-2", {"file_path": "memory.md"}),
            _tool_end("read_file", "r-2", "长期偏好内容"),
            _tool_end("read_file", "r-1", "画像内容"),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        starts = [e for e in collected if e["type"] == "tool_start"]
        ends = [e for e in collected if e["type"] == "tool_end"]
        ids = [e["data"]["id"] for e in starts]
        assert ids == ["tc_001", "tc_002"]
        # end 顺序跟 start 顺序相反（r-2 先结束），验证按 run_id 而非按顺序配对
        pair = {e["data"]["id"]: e["data"]["result_summary"] for e in ends}
        assert pair == {"tc_001": "画像内容", "tc_002": "长期偏好内容"}

    @pytest.mark.asyncio
    async def test_error_path_sets_status_error(self, monkeypatch):
        """工具异常走 on_tool_error → tool_end(status='error')，不落 ok"""
        events = [
            _tool_start("search_jobs", "r-1", {"location": "上海"}),
            _tool_error("search_jobs", "r-1", "数据库连接失败"),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        ends = [e for e in collected if e["type"] == "tool_end"]
        assert len(ends) == 1
        assert ends[0]["data"]["status"] == "error"
        assert ends[0]["data"]["result_summary"] == "数据库连接失败"
        tool_events = next(e for e in collected if e["type"] == "tool_events")
        assert tool_events["data"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_result_summary_truncated_to_limit(self, monkeypatch):
        """非专用工具的 result_summary 截断到 200 字符上限"""
        long_output = "x" * 500
        events = [
            _tool_start("ls", "r-1", {"path": "/"}),
            _tool_end("ls", "r-1", long_output),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        ends = [e for e in collected if e["type"] == "tool_end"]
        assert len(ends[0]["data"]["result_summary"]) == 200

    @pytest.mark.asyncio
    async def test_unfinished_start_not_persisted_in_tool_events(self, monkeypatch):
        """只有 start 没有 end（如中途异常）：tool_events 不收录，避免历史出现永远 running 的假行"""
        events = [
            _tool_start("search_jobs", "r-1", {"location": "深圳"}),
            _tool_start("read_file", "r-2", {"file_path": "profile.md"}),
            _tool_end("read_file", "r-2", "画像内容"),
        ]
        agent = _make_agent(monkeypatch, events)
        collected = await _collect(agent)

        tool_events = next(e for e in collected if e["type"] == "tool_events")
        assert [ev["id"] for ev in tool_events["data"]] == ["tc_002"]
        # 但 tool_calls 批量事件仍包含两个调用（现状行为不变，只有新的 tool_events 过滤了 running）
        tool_calls = next(e for e in collected if e["type"] == "tool_calls")
        assert len(tool_calls["data"]) == 2
