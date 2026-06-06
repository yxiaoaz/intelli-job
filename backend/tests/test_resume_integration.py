"""
Integration tests for resume processing pipeline
"""
import pytest
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import UploadFile

from app.services.resume_upload_service import ResumeUploadService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_evaluation_service import ResumeEvaluationService


class TestResumeProcessingPipeline:
    """简历处理流水线集成测试"""
    
    @pytest.fixture
    def upload_service(self, tmp_path):
        return ResumeUploadService(storage_root=str(tmp_path))
    
    @pytest.fixture
    def parser_service(self):
        return ResumeParserService()
    
    @pytest.fixture
    def evaluation_service(self):
        return ResumeEvaluationService()
    
    @pytest.fixture
    def mock_pdf_file(self):
        file = Mock(spec=UploadFile)
        file.filename = "test_resume.pdf"
        file.content_type = "application/pdf"
        file.size = 1024 * 100
        file.read = AsyncMock(return_value=b"%PDF-1.4 fake content")
        return file
    
    @pytest.mark.asyncio
    async def test_full_pipeline_upload_parse_evaluate(
        self,
        upload_service,
        parser_service,
        evaluation_service,
        mock_pdf_file,
        tmp_path
    ):
        """测试完整流程：上传 → 解析 → 评估"""
        user_id = uuid.uuid4()
        
        # Step 1: 上传文件
        file_info = await upload_service.save_file(mock_pdf_file, user_id)
        
        assert "file_path" in file_info
        assert Path(file_info["file_path"]).exists()
        
        # Step 2: Mock 文本提取
        extracted_text = """
        John Doe
        Software Engineer
        
        Experience:
        - Senior Developer at Tech Corp (2020-2023)
          Developed web applications using Python and React
        
        Education:
        - BS Computer Science, University of Technology
        
        Skills: Python, JavaScript, React, SQL
        """
        
        with patch.object(parser_service, 'extract_text') as mock_extract:
            mock_extract.return_value = extracted_text
            
            # Step 3: Mock LLM 解析
            parsed_data = {
                "personal_info": {
                    "name": "John Doe",
                    "email": "john@example.com"
                },
                "work_experience": [
                    {
                        "company": "Tech Corp",
                        "position": "Senior Developer",
                        "description": "Developed web applications"
                    }
                ],
                "education": [
                    {"school": "University", "degree": "BS", "major": "CS"}
                ],
                "skills": ["Python", "JavaScript", "React", "SQL"],
                "projects": []
            }
            
            with patch.object(parser_service.llm_service, 'generate_completion') as mock_chat:
                import json
                mock_chat.return_value = json.dumps(parsed_data)
                
                # 执行解析
                result = await parser_service.parse_with_llm(extracted_text)
                
                assert result == parsed_data
                
                # Step 4: 生成评估报告
                expected_eval = {
                    "overall_score": 85,
                    "dimension_scores": {
                        "completeness": 80,
                        "professionalism": 85,
                        "relevance": 90,
                        "formatting": 85
                    },
                    "summary": "Excellent resume with strong technical background",
                    "suggestions": [
                        {
                            "category": "Projects",
                            "issue": "No projects listed",
                            "recommendation": "Add personal or open-source projects"
                        }
                    ],
                    "strengths": ["Strong technical skills", "Clear work experience"]
                }
                
                with patch.object(evaluation_service.llm_service, 'generate_completion') as eval_chat:
                    eval_chat.return_value = json.dumps(expected_eval)
                    
                    evaluation = await evaluation_service.generate_evaluation_report(result)
                    
                    assert evaluation["overall_score"] == 85
                    assert len(evaluation["suggestions"]) > 0
                    assert "strengths" in evaluation
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling_invalid_file(
        self,
        upload_service,
        mock_pdf_file
    ):
        """测试流水线错误处理 - 无效文件"""
        user_id = uuid.uuid4()
        
        # 模拟文件读取失败
        mock_pdf_file.read = AsyncMock(side_effect=IOError("Read error"))
        
        with pytest.raises(IOError):
            await upload_service.save_file(mock_pdf_file, user_id)
    
    @pytest.mark.asyncio
    async def test_pipeline_error_handling_parse_failure(
        self,
        parser_service
    ):
        """测试流水线错误处理 - 解析失败"""
        resume_text = "Invalid resume content"
        
        with patch.object(parser_service.llm_service, 'generate_completion') as mock_chat:
            mock_chat.side_effect = Exception("LLM service unavailable")
            
            with pytest.raises(Exception):
                await parser_service.parse_with_llm(resume_text)
    
    @pytest.mark.asyncio
    async def test_pipeline_consistency_multiple_resumes(
        self,
        upload_service,
        parser_service,
        evaluation_service,
        tmp_path
    ):
        """测试多个简历处理的一致性"""
        results = []
        
        for i in range(3):
            # 创建模拟文件
            file = Mock(spec=UploadFile)
            file.filename = f"resume_{i}.pdf"
            file.content_type = "application/pdf"
            file.size = 1024 * 100
            file.read = AsyncMock(return_value=b"%PDF-1.4 content")
            
            user_id = uuid.uuid4()
            
            # 上传
            file_info = await upload_service.save_file(file, user_id)
            assert Path(file_info["file_path"]).exists()
            
            results.append(file_info)
        
        # 验证所有文件都成功保存
        assert len(results) == 3
        for result in results:
            assert "filename" in result
            assert "file_path" in result
    
    def test_services_initialization(self):
        """测试服务初始化"""
        upload_service = ResumeUploadService()
        parser_service = ResumeParserService()
        evaluation_service = ResumeEvaluationService()
        
        assert upload_service is not None
        assert parser_service is not None
        assert evaluation_service is not None
        assert parser_service.llm_service is not None
        assert evaluation_service.llm_service is not None
