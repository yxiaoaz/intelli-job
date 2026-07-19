"""
Tests for AliyunEmbeddings async functionality
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, Mock
from app.services.aliyun_embeddings import AliyunEmbeddings


class TestAliyunEmbeddingsAsync:
    """Test async embedding methods"""
    
    @pytest.fixture
    def embeddings(self):
        """Create AliyunEmbeddings instance with test config"""
        return AliyunEmbeddings(api_key="test_key", timeout=5)
    
    @pytest.mark.asyncio
    async def test_aembed_query_success(self, embeddings):
        """Test async embed_query returns valid embedding"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }
        
        # Mock the async client
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            result = await embeddings.aembed_query("test text")
            
            assert isinstance(result, list)
            assert len(result) == 3
            assert result == [0.1, 0.2, 0.3]
    
    @pytest.mark.asyncio
    async def test_aembed_query_timeout(self, embeddings):
        """Test timeout handling in async embed_query"""
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            with pytest.raises(TimeoutError, match="timed out"):
                await embeddings.aembed_query("test text")
    
    @pytest.mark.asyncio
    async def test_aembed_query_connection_error(self, embeddings):
        """Test connection error handling"""
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await embeddings.aembed_query("test text")
    
    @pytest.mark.asyncio
    async def test_aembed_query_empty_text(self, embeddings):
        """Test validation of empty text"""
        with pytest.raises(ValueError, match="cannot be empty"):
            await embeddings.aembed_query("")
    
    @pytest.mark.asyncio
    async def test_aembed_query_api_error(self, embeddings):
        """Test API error handling (non-200 status)"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            with pytest.raises(Exception, match="API request failed"):
                await embeddings.aembed_query("test text")
    
    @pytest.mark.asyncio
    async def test_aembed_documents_concurrent(self, embeddings):
        """Test batch processing with concurrency"""
        texts = ["text1", "text2", "text3"]
        
        # Mock responses for each text
        mock_responses = [
            {"data": [{"embedding": [0.1, 0.2]}]},
            {"data": [{"embedding": [0.3, 0.4]}]},
            {"data": [{"embedding": [0.5, 0.6]}]},
        ]
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.is_closed = False
            
            # Create mock responses
            responses = []
            for resp_data in mock_responses:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = resp_data
                responses.append(mock_resp)
            
            mock_client_instance.post = AsyncMock(side_effect=responses)
            MockClient.return_value = mock_client_instance
            
            results = await embeddings.aembed_documents(texts)
            
            assert len(results) == 3
            assert all(isinstance(r, list) for r in results)
            assert results[0] == [0.1, 0.2]
            assert results[1] == [0.3, 0.4]
            assert results[2] == [0.5, 0.6]
    
    @pytest.mark.asyncio
    async def test_aembed_documents_partial_failure(self, embeddings):
        """Test batch processing with some failures"""
        texts = ["text1", "text2", "text3"]
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.is_closed = False
            
            # First succeeds, second fails, third succeeds
            success_resp = Mock()
            success_resp.status_code = 200
            success_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
            
            fail_resp = Mock()
            fail_resp.status_code = 500
            fail_resp.text = "Internal Server Error"
            
            mock_client_instance.post = AsyncMock(side_effect=[success_resp, fail_resp, success_resp])
            MockClient.return_value = mock_client_instance
            
            results = await embeddings.aembed_documents(texts)
            
            # Should have 2 successful results (failures are filtered out)
            assert len(results) == 2
            assert all(isinstance(r, list) for r in results)
    
    @pytest.mark.asyncio
    async def test_async_client_reuse(self, embeddings):
        """Test that async client is reused across calls"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            # First call - should create client
            await embeddings.aembed_query("text1")
            first_call_count = MockClient.call_count
            
            # Second call - should reuse client
            await embeddings.aembed_query("text2")
            second_call_count = MockClient.call_count
            
            # Client should only be created once
            assert first_call_count == 1
            assert second_call_count == 1  # Not incremented


class TestAliyunEmbeddingsSync:
    """Test that sync methods still work (backward compatibility)"""
    
    @pytest.fixture
    def embeddings(self):
        return AliyunEmbeddings(api_key="test_key", timeout=5)
    
    def test_sync_embed_query_exists(self, embeddings):
        """Verify sync method still exists"""
        assert hasattr(embeddings, 'embed_query')
        assert callable(embeddings.embed_query)
    
    def test_sync_embed_documents_exists(self, embeddings):
        """Verify sync batch method still exists"""
        assert hasattr(embeddings, 'embed_documents')
        assert callable(embeddings.embed_documents)
