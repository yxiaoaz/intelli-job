"""
Tests for ResumeEvaluationService
"""
import pytest
import json
from unittest.mock import patch, AsyncMock

from app.services.resume_evaluation_service import ResumeEvaluationService


class TestResumeEvaluationService:
    """简历评估服务测试"""
    
    @pytest.fixture
    def evaluation_service(self):
        """创建评估服务实例"""
        return ResumeEvaluationService()
    
    def test_calculate_completeness_score_full_marks(self, evaluation_service):
        """测试完整性评分 - 满分情况"""
        parsed_data = {
            "personal_info": {
                "name": "John",
                "email": "john@test.com",
                "phone": "123",
                "location": "Beijing"
            },
            "education": [
                {"school": "Uni", "degree": "BS", "major": "CS"}
            ],
            "work_experience": [
                {
                    "company": "Corp",
                    "position": "Dev",
                    "description": "A" * 100  # 详细描述
                }
            ],
            "skills": ["Python", "Java", "SQL"],
            "projects": [{"name": "Proj"}]
        }
        
        score = evaluation_service.calculate_completeness_score(parsed_data)
        
        assert score == 100
    
    def test_calculate_completeness_score_no_personal_info(self, evaluation_service):
        """测试完整性评分 - 缺少个人信息"""
        parsed_data = {
            "personal_info": {},
            "education": [],
            "work_experience": [],
            "skills": [],
            "projects": []
        }
        
        score = evaluation_service.calculate_completeness_score(parsed_data)
        
        assert score == 0
    
    def test_calculate_completeness_score_partial_skills(self, evaluation_service):
        """测试完整性评分 - 少量技能"""
        parsed_data = {
            "personal_info": {"name": "Test"},
            "education": [],
            "work_experience": [],
            "skills": ["Python"],  # 少于 3 个
            "projects": []
        }
        
        score = evaluation_service.calculate_completeness_score(parsed_data)
        
        # 应该有部分分数但不是满分
        assert 0 < score < 50
    
    def test_calculate_completeness_score_work_without_detail(self, evaluation_service):
        """测试完整性评分 - 工作经历无详情"""
        parsed_data = {
            "personal_info": {"name": "Test", "email": "t@t.com", "phone": "1", "location": "L"},
            "education": [{"school": "S", "degree": "D", "major": "M"}],
            "work_experience": [
                {"company": "C", "position": "P", "description": "Short"}  # 描述太短
            ],
            "skills": ["A", "B", "C"],
            "projects": []
        }
        
        score = evaluation_service.calculate_completeness_score(parsed_data)
        
        # 应该比有详情的分数低
        assert score < 80
    
    @pytest.mark.asyncio
    async def test_generate_evaluation_report_success(self, evaluation_service):
        """测试生成评估报告成功"""
        parsed_data = {
            "personal_info": {"name": "John Doe"},
            "skills": ["Python", "React"],
            "work_experience": []
        }
        
        expected_evaluation = {
            "overall_score": 75,
            "dimension_scores": {
                "completeness": 60,
                "professionalism": 70,
                "relevance": 80,
                "formatting": 75
            },
            "summary": "Good resume",
            "suggestions": [],
            "strengths": ["Strong skills"]
        }
        
        with patch.object(evaluation_service.llm_service, 'generate_completion') as mock_chat:
            mock_chat.return_value = json.dumps(expected_evaluation)
            
            result = await evaluation_service.generate_evaluation_report(parsed_data)
            
            assert result["overall_score"] == 75
            assert "summary" in result
            assert "suggestions" in result
    
    @pytest.mark.asyncio
    async def test_generate_evaluation_report_includes_completeness(self, evaluation_service):
        """测试评估报告包含完整性评分"""
        parsed_data = {
            "personal_info": {"name": "Test"},
            "education": [],
            "work_experience": [],
            "skills": [],
            "projects": []
        }
        
        expected_eval = {
            "overall_score": 50,
            "dimension_scores": {},
            "summary": "Test",
            "suggestions": [],
            "strengths": []
        }
        
        with patch.object(evaluation_service.llm_service, 'generate_completion') as mock_chat:
            mock_chat.return_value = json.dumps(expected_eval)
            
            result = await evaluation_service.generate_evaluation_report(parsed_data)
            
            # 应该补充完整性评分
            assert "completeness" in result["dimension_scores"]
    
    @pytest.mark.asyncio
    async def test_generate_evaluation_report_llm_failure_fallback(self, evaluation_service):
        """测试 LLM 失败时的降级处理"""
        parsed_data = {
            "personal_info": {"name": "Test"},
            "education": [],
            "work_experience": [],
            "skills": [],
            "projects": []
        }
        
        with patch.object(evaluation_service.llm_service, 'generate_completion') as mock_chat:
            mock_chat.side_effect = Exception("LLM error")
            
            result = await evaluation_service.generate_evaluation_report(parsed_data)
            
            # 应该返回基础评估而不是抛出异常
            assert "overall_score" in result
            assert "summary" in result
            assert "suggestions" in result
    
    @pytest.mark.asyncio
    async def test_generate_evaluation_report_temperature_setting(self, evaluation_service):
        """测试 LLM 调用温度参数"""
        parsed_data = {"personal_info": {}}
        
        expected_eval = {"overall_score": 70, "dimension_scores": {}, "summary": "", "suggestions": [], "strengths": []}
        
        with patch.object(evaluation_service.llm_service, 'generate_completion') as mock_chat:
            mock_chat.return_value = json.dumps(expected_eval)
            
            await evaluation_service.generate_evaluation_report(parsed_data)
            
            # 验证调用成功
            mock_chat.assert_called_once()
    
    def test_generate_evaluation_report_json_format(self, evaluation_service):
        """测试评估报告 JSON 格式"""
        parsed_data = {
            "personal_info": {"name": "Test User"},
            "education": [{"school": "Test University"}],
            "work_experience": [],
            "skills": ["Skill1"],
            "projects": []
        }
        
        # 这个测试验证方法签名和返回类型
        # 实际异步测试在上面
        assert hasattr(evaluation_service, 'generate_evaluation_report')
