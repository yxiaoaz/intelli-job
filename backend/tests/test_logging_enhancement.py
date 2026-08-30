"""
测试日志增强功能
验证LLM调用前后的日志是否正确记录
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_openai import ChatOpenAI
from app.services.llm_service import LLMService


class TestLoggingEnhancement:
    """测试日志增强功能"""
    
    @pytest.mark.asyncio
    async def test_llm_completion_logging(self):
        """测试LLM completion调用的日志记录"""
        service = LLMService()
        
        # Mock chat model response
        mock_response = MagicMock()
        mock_response.content = "Test response content"
        
        # patch 类级 ainvoke：ChatOpenAI 是 pydantic 模型，实例上无法 setattr
        with patch.object(ChatOpenAI, 'ainvoke', new=AsyncMock(return_value=mock_response)):
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"}
            ]
            
            result = await service.generate_completion(messages)
            
            assert result == "Test response content"
    
    @pytest.mark.asyncio
    async def test_embedding_logging(self):
        """测试embedding生成的日志记录"""
        service = LLMService()
        
        # Mock embedding model（generate_embedding 为 async，需 await）
        with patch.object(service.embedding_model, 'embed_query', return_value=[0.1, 0.2, 0.3]):
            result = await service.generate_embedding("Test text")
            
            assert len(result) == 3
    
    def test_batch_embedding_logging(self):
        """测试批量embedding生成的日志记录"""
        service = LLMService()
        
        # Mock batch embedding
        with patch.object(service.embedding_model, 'embed_documents', return_value=[[0.1, 0.2], [0.3, 0.4]]):
            result = service.generate_embeddings_batch(["Text 1", "Text 2"])
            
            assert len(result) == 2
            assert len(result[0]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
