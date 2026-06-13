"""
Conversation Agent Tests

Tests for:
- Chat endpoint
- Message history
- AI responses
"""
import pytest
import pytest_asyncio


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
