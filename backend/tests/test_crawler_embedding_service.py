"""
Tests for CrawlerEmbeddingService async functionality
"""
import pytest
import httpx
import json
from unittest.mock import AsyncMock, patch, Mock
from app.services.crawler_embedding_service import CrawlerEmbeddingService


class TestCrawlerEmbeddingServiceAsync:
    """Test async embedding methods"""
    
    @pytest.fixture
    def service(self):
        """Create CrawlerEmbeddingService instance with test config"""
        return CrawlerEmbeddingService(api_key="test_key", timeout=5)
    
    @pytest.mark.asyncio
    async def test_aget_single_embedding_success(self, service):
        """Test async get_single_embedding returns valid embedding"""
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
            
            result = await service.aget_single_embedding("test text")
            
            assert isinstance(result, list)
            assert len(result) == 3
            assert result == [0.1, 0.2, 0.3]
    
    @pytest.mark.asyncio
    async def test_aget_single_embedding_api_error(self, service):
        """Test error handling when API returns error status"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.is_closed = False
            MockClient.return_value = mock_client_instance
            
            with pytest.raises(Exception, match="status 401"):
                await service.aget_single_embedding("test text")
    
    @pytest.mark.asyncio
    async def test_aget_embedding_batch_concurrency(self, service, tmp_path):
        """Test batch processing with concurrency limit"""
        # Create test input file
        input_file = tmp_path / "input.jsonl"
        input_data = [
            {"custom_id": "1", "body": {"input": "text1"}},
            {"custom_id": "2", "body": {"input": "text2"}},
            {"custom_id": "3", "body": {"input": "text3"}},
        ]
        input_file.write_text('\n'.join(json.dumps(item) for item in input_data))
        
        output_file = tmp_path / "output.jsonl"
        
        # Mock responses
        mock_responses = [
            {"data": [{"embedding": [0.1, 0.2]}]},
            {"data": [{"embedding": [0.3, 0.4]}]},
            {"data": [{"embedding": [0.5, 0.6]}]},
        ]
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.is_closed = False
            
            # Create mock responses
            mock_resps = []
            for resp_data in mock_responses:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = resp_data
                mock_resps.append(mock_resp)
            
            mock_client_instance.post = AsyncMock(side_effect=mock_resps)
            MockClient.return_value = mock_client_instance
            
            results = await service.aget_embedding_batch(
                str(input_file),
                str(output_file),
                concurrency=2
            )
            
            assert len(results) == 3
            assert all(isinstance(r["embedding"], list) for r in results)
            assert output_file.exists()
    
    @pytest.mark.asyncio
    async def test_aget_embedding_batch_partial_failure(self, service, tmp_path):
        """Test batch processing handles partial failures gracefully"""
        # Create test input file
        input_file = tmp_path / "input.jsonl"
        input_data = [
            {"custom_id": "1", "body": {"input": "text1"}},
            {"custom_id": "2", "body": {"input": ""}},  # Empty input
            {"custom_id": "3", "body": {"input": "text3"}},
        ]
        input_file.write_text('\n'.join(json.dumps(item) for item in input_data))
        
        output_file = tmp_path / "output.jsonl"
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.is_closed = False
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client_instance
            
            results = await service.aget_embedding_batch(
                str(input_file),
                str(output_file),
                concurrency=2
            )
            
            # Should skip empty input, so only 2 results
            assert len(results) == 2
            assert all(r["id"] in ["1", "3"] for r in results)
    
    @pytest.mark.asyncio
    async def test_async_client_reuse(self, service):
        """Test that async client is reused across calls"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.is_closed = False
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client_instance
            
            # Call multiple times
            await service.aget_single_embedding("text1")
            await service.aget_single_embedding("text2")
            
            # Client should be created only once
            assert MockClient.call_count == 1


class TestCrawlerEmbeddingServiceSync:
    """Test sync methods still work"""
    
    @pytest.fixture
    def service(self):
        """Create CrawlerEmbeddingService instance"""
        return CrawlerEmbeddingService(api_key="test_key", timeout=5)
    
    def test_sync_get_single_embedding_exists(self, service):
        """Verify sync method exists and has correct signature"""
        assert hasattr(service, '_get_single_embedding')
        assert callable(service._get_single_embedding)
    
    def test_sync_get_embedding_batch_exists(self, service):
        """Verify sync batch method exists"""
        assert hasattr(service, 'get_embedding_batch')
        assert callable(service.get_embedding_batch)
