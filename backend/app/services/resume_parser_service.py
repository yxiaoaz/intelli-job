"""
简历解析服务
从 PDF/DOCX 文件中提取文本并使用 LLM 进行结构化解析
"""
import json
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService
from app.models import Resume, ResumeAnalysis
from app.utils.logger import get_logger

logger = get_logger()


class ResumeParserService:
    """简历解析服务"""
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        从 PDF 文件提取文本
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            str: 提取的文本内容
            
        Raises:
            Exception: 提取失败时抛出
        """
        try:
            import PyPDF2
            
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                
                # 检查是否加密
                if reader.is_encrypted:
                    raise ValueError("无法解析加密的 PDF 文件，请提供未加密版本")
                
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if not text.strip():
                raise ValueError("PDF 文件中未找到文本内容")
            
            logger.info(f"成功从 PDF 提取文本，长度: {len(text)} 字符")
            return text
            
        except ImportError:
            logger.error("PyPDF2 未安装")
            raise ImportError("请安装 PyPDF2: pip install PyPDF2")
        except Exception as e:
            logger.error(f"PDF 文本提取失败: {e}")
            raise
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """
        从 DOCX 文件提取文本
        
        Args:
            file_path: DOCX 文件路径
            
        Returns:
            str: 提取的文本内容
            
        Raises:
            Exception: 提取失败时抛出
        """
        try:
            from docx import Document
            
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            if not text.strip():
                raise ValueError("DOCX 文件中未找到文本内容")
            
            logger.info(f"成功从 DOCX 提取文本，长度: {len(text)} 字符")
            return text
            
        except ImportError:
            logger.error("python-docx 未安装")
            raise ImportError("请安装 python-docx: pip install python-docx")
        except Exception as e:
            logger.error(f"DOCX 文本提取失败: {e}")
            raise
    
    def extract_text(self, file_path: str, content_type: str) -> str:
        """
        根据文件类型提取文本
        
        Args:
            file_path: 文件路径
            content_type: MIME 类型
            
        Returns:
            str: 提取的文本内容
        """
        if content_type == "application/pdf":
            return self.extract_text_from_pdf(file_path)
        elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {content_type}")
    
    async def parse_with_llm(self, resume_text: str) -> dict:
        """
        使用 LLM 解析简历文本为结构化数据
        
        Args:
            resume_text: 简历文本内容
            
        Returns:
            dict: 结构化解析结果
        """
        logger.info(
            "resume_parsing_start",
            text_length=len(resume_text),
            text_preview=resume_text[:200]
        )
        
        # 构建提示词
        system_prompt = """你是一个专业的简历解析助手。请将简历文本解析为结构化的 JSON 格式。

要求：
1. 提取所有可用信息，如果某项信息不存在则设为 null 或空数组
2. 保持原文的语言（中文或英文）
3. 日期格式统一为 YYYY-MM 或 YYYY
4. 技能列表要尽可能详细

输出格式必须严格遵循以下 JSON Schema：
{
  "personal_info": {
    "name": "姓名",
    "email": "邮箱",
    "phone": "电话",
    "location": "地点"
  },
  "education": [
    {
      "school": "学校名称",
      "degree": "学位",
      "major": "专业",
      "start_date": "开始时间",
      "end_date": "结束时间",
      "gpa": "GPA（可选）"
    }
  ],
  "work_experience": [
    {
      "company": "公司名称",
      "position": "职位",
      "start_date": "开始时间",
      "end_date": "结束时间",
      "description": "工作描述（包含主要职责和成就）"
    }
  ],
  "skills": ["技能1", "技能2", "..."],
  "projects": [
    {
      "name": "项目名称",
      "description": "项目描述",
      "technologies": ["技术1", "技术2"]
    }
  ],
  "certifications": ["证书1", "证书2"],
  "languages": ["语言1", "语言2"]
}

只返回 JSON，不要添加任何其他文本。"""

        user_prompt = f"""请解析以下简历内容：

{resume_text}
"""

        try:
            logger.info("calling_llm_for_resume_parsing")
            
            # 调用 LLM
            response = await self.llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            logger.info(
                "llm_response_received",
                response_length=len(response),
                response_preview=response[:200]
            )
            
            # 解析 JSON
            parsed_data = json.loads(response)
            
            logger.info(
                "resume_parsing_success",
                has_personal_info=bool(parsed_data.get("personal_info", {}).get("name")),
                education_count=len(parsed_data.get("education", [])),
                work_experience_count=len(parsed_data.get("work_experience", [])),
                skills_count=len(parsed_data.get("skills", []))
            )
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(
                "llm_response_invalid_json",
                error=str(e),
                response_preview=response[:500] if 'response' in locals() else ""
            )
            raise ValueError(f"解析结果格式错误: {e}")
        except Exception as e:
            logger.error("resume_parsing_failed", error=str(e))
            raise
    
    async def create_analysis_record(
        self,
        session: AsyncSession,
        resume_id: str,
        parsed_data: dict,
        status: str = "completed",
        error_message: Optional[str] = None
    ) -> ResumeAnalysis:
        """
        创建简历分析记录
        
        Args:
            session: 数据库会话
            resume_id: 简历ID
            parsed_data: 解析后的结构化数据
            status: 分析状态
            error_message: 错误信息（如果失败）
            
        Returns:
            ResumeAnalysis: 创建的分析记录
        """
        analysis = ResumeAnalysis(
            resume_id=resume_id,
            parsed_data=parsed_data,
            status=status,
            error_message=error_message,
        )
        
        session.add(analysis)
        await session.flush()
        
        logger.info(f"简历分析记录已创建: analysis_id={analysis.id}, status={status}")
        return analysis
    
    async def update_analysis_status(
        self,
        session: AsyncSession,
        analysis_id: str,
        status: str,
        parsed_data: Optional[dict] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        更新分析记录状态
        
        Args:
            session: 数据库会话
            analysis_id: 分析记录ID
            status: 新状态
            parsed_data: 解析数据（可选）
            error_message: 错误信息（可选）
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(ResumeAnalysis).where(ResumeAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        
        if analysis:
            analysis.status = status
            if parsed_data:
                analysis.parsed_data = parsed_data
            if error_message:
                analysis.error_message = error_message
            
            logger.info(f"分析记录状态已更新: analysis_id={analysis_id}, status={status}")
