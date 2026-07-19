"""
Tests for Pydantic v2 schema compatibility in resumes API
"""
import pytest
from datetime import datetime
from app.api.v1.resumes import ResumeResponse, AnalysisResponse


class TestResumeResponsePydanticV2:
    """Test ResumeResponse uses Pydantic v2 syntax"""
    
    def test_resume_response_serialization(self):
        """Test that ResumeResponse works with Pydantic v2"""
        response = ResumeResponse(
            id="123",
            filename="test.pdf",
            file_size=1024,
            content_type="application/pdf",
            uploaded_at=datetime.now().isoformat(),
            status="completed",
            score=85,
            is_default=False
        )
        
        # Should serialize without errors using model_dump (v2 method)
        data = response.model_dump()
        assert data["id"] == "123"
        assert data["filename"] == "test.pdf"
        assert data["file_size"] == 1024
        assert data["content_type"] == "application/pdf"
        assert data["status"] == "completed"
        assert data["score"] == 85
        assert data["is_default"] is False
    
    def test_resume_response_model_config(self):
        """Verify model_config is set correctly"""
        assert hasattr(ResumeResponse, 'model_config')
        assert ResumeResponse.model_config.get('from_attributes') is True
    
    def test_resume_response_json(self):
        """Test JSON serialization"""
        response = ResumeResponse(
            id="456",
            filename="resume.docx",
            file_size=2048,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            uploaded_at="2026-07-18T10:00:00",
            status="pending",
            score=None,
            is_default=True
        )
        
        json_str = response.model_dump_json()
        assert "456" in json_str
        assert "resume.docx" in json_str


class TestAnalysisResponsePydanticV2:
    """Test AnalysisResponse uses Pydantic v2 syntax"""
    
    def test_analysis_response_serialization(self):
        """Test that AnalysisResponse works with Pydantic v2"""
        response = AnalysisResponse(
            id="analysis-123",
            resume_id="resume-456",
            parsed_data={"name": "John Doe", "email": "john@example.com"},
            evaluation={"score": 90, "feedback": "Excellent"},
            status="completed",
            error_message=None
        )
        
        # Should serialize without errors using model_dump (v2 method)
        data = response.model_dump()
        assert data["id"] == "analysis-123"
        assert data["resume_id"] == "resume-456"
        assert data["parsed_data"]["name"] == "John Doe"
        assert data["evaluation"]["score"] == 90
        assert data["status"] == "completed"
        assert data["error_message"] is None
    
    def test_analysis_response_model_config(self):
        """Verify model_config is set correctly"""
        assert hasattr(AnalysisResponse, 'model_config')
        assert AnalysisResponse.model_config.get('from_attributes') is True
    
    def test_analysis_response_with_error(self):
        """Test response with error message"""
        response = AnalysisResponse(
            id="analysis-789",
            resume_id="resume-000",
            parsed_data=None,
            evaluation=None,
            status="failed",
            error_message="Processing failed due to invalid format"
        )
        
        data = response.model_dump()
        assert data["status"] == "failed"
        assert "Processing failed" in data["error_message"]
        assert data["parsed_data"] is None


class TestNoDeprecatedConfigClass:
    """Ensure old class Config syntax is not used"""
    
    def test_resume_response_no_class_config(self):
        """Verify ResumeResponse doesn't use deprecated class Config"""
        # Check that there's no Config class in the class dict
        assert 'Config' not in ResumeResponse.__dict__
    
    def test_analysis_response_no_class_config(self):
        """Verify AnalysisResponse doesn't use deprecated class Config"""
        assert 'Config' not in AnalysisResponse.__dict__
