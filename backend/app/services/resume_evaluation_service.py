"""
简历评估服务
对解析后的简历进行质量评分和生成改进建议
"""
import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService
from app.models import ResumeAnalysis
from app.utils.logger import get_logger

logger = get_logger()


class ResumeEvaluationService:
    """简历评估服务"""
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def calculate_completeness_score(self, parsed_data: dict) -> float:
        """
        计算内容完整性评分（0-100）
        
        Args:
            parsed_data: 结构化解析数据
            
        Returns:
            float: 完整性评分
        """
        score = 0.0
        max_score = 100.0
        
        # 个人信息 (20分)
        personal_info = parsed_data.get("personal_info", {})
        if personal_info.get("name"):
            score += 5
        if personal_info.get("email"):
            score += 5
        if personal_info.get("phone"):
            score += 5
        if personal_info.get("location"):
            score += 5
        
        # 教育背景 (20分)
        education = parsed_data.get("education", [])
        if len(education) > 0:
            score += 10
            for edu in education:
                if edu.get("school") and edu.get("degree") and edu.get("major"):
                    score += 10
                    break
        
        # 工作经历 (30分)
        work_experience = parsed_data.get("work_experience", [])
        if len(work_experience) > 0:
            score += 15
            # 检查是否有详细描述
            has_detail = any(len(exp.get("description", "")) > 50 for exp in work_experience)
            if has_detail:
                score += 15
        
        # 技能列表 (15分)
        skills = parsed_data.get("skills", [])
        if len(skills) >= 3:
            score += 15
        elif len(skills) > 0:
            score += 7
        
        # 项目经验 (15分)
        projects = parsed_data.get("projects", [])
        if len(projects) > 0:
            score += 15
        
        return min(score, max_score)
    
    async def generate_evaluation_report(self, parsed_data: dict) -> dict:
        """
        生成完整的评估报告
        
        Args:
            parsed_data: 结构化解析数据
            
        Returns:
            dict: 评估报告，包含总分、各维度评分和改进建议
        """
        logger.info(
            "resume_evaluation_start",
            has_personal_info=bool(parsed_data.get("personal_info", {}).get("name")),
            education_count=len(parsed_data.get("education", [])),
            work_experience_count=len(parsed_data.get("work_experience", [])),
            skills_count=len(parsed_data.get("skills", []))
        )
        
        # 计算完整性评分
        completeness_score = self.calculate_completeness_score(parsed_data)
        
        logger.info(f"completeness_score_calculated: {completeness_score}")
        
        # 使用 LLM 生成详细评估和建议
        system_prompt = """你是一个专业的简历评估专家。请基于提供的简历数据生成评估报告。

要求：
1. 语气专业、友好、建设性
2. 建议要具体、可操作，避免泛泛而谈
3. 突出优点，同时指出改进空间
4. 使用中文回复

输出格式必须是 JSON：
{
  "overall_score": 85,
  "dimension_scores": {
    "completeness": 90,
    "professionalism": 80,
    "relevance": 85,
    "formatting": 85
  },
  "summary": "总体评语（200-300字）",
  "suggestions": [
    {
      "category": "工作经历",
      "issue": "问题描述",
      "recommendation": "具体改进建议"
    }
  ],
  "strengths": ["优势1", "优势2"]
}"""

        user_prompt = f"""请评估以下简历数据：

{json.dumps(parsed_data, ensure_ascii=False, indent=2)}

完整性评分参考：{completeness_score}/100

请生成详细的评估报告。"""

        try:
            logger.info("calling_llm_for_resume_evaluation")
            
            response = await self.llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            logger.info(
                "llm_evaluation_response_received",
                response_length=len(response),
                response_preview=response[:200]
            )
            
            evaluation = json.loads(response)
            
            # 补充完整性评分
            evaluation["dimension_scores"]["completeness"] = completeness_score
            
            logger.info(
                "resume_evaluation_success",
                overall_score=evaluation.get('overall_score'),
                suggestions_count=len(evaluation.get('suggestions', [])),
                strengths_count=len(evaluation.get('strengths', []))
            )
            
            return evaluation
            
        except Exception as e:
            logger.error(f"评估报告生成失败: {e}")
            # 返回基础评估
            return {
                "overall_score": int(completeness_score),
                "dimension_scores": {
                    "completeness": completeness_score,
                    "professionalism": 70,
                    "relevance": 70,
                    "formatting": 70,
                },
                "summary": "简历已解析完成，建议进一步完善内容以提升竞争力。",
                "suggestions": [
                    {
                        "category": "内容完善",
                        "issue": "建议补充更多细节",
                        "recommendation": "添加量化成果和具体项目描述"
                    }
                ],
                "strengths": ["基本信息完整"]
            }
    
    async def update_analysis_with_evaluation(
        self,
        session: AsyncSession,
        analysis_id: str,
        evaluation: dict
    ) -> None:
        """
        将评估报告更新到分析记录
        
        Args:
            session: 数据库会话
            analysis_id: 分析记录ID
            evaluation: 评估报告
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(ResumeAnalysis).where(ResumeAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        
        if analysis:
            analysis.evaluation = evaluation
            logger.info(f"评估报告已保存到分析记录: analysis_id={analysis_id}")
