"""
AI 岗位解释服务
分析岗位描述与用户简历的匹配度，生成结构化解释（带缓存）
"""
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobAIExplanation, JobItem, Resume
from app.services.llm_service import LLMService
from app.services.query_enhancer import extract_resume_profile
from app.utils.logger import get_logger

logger = get_logger()


class JobAIExplanationService:
    """AI 岗位解释服务 — 按需生成 + 数据库缓存"""

    def __init__(self):
        self.llm_service = LLMService()

    async def generate_explanation(
        self, user_id, job_id: str, db: AsyncSession
    ) -> dict:
        """获取岗位的 AI 解释（优先读缓存，未命中则调用 LLM 生成）

        Args:
            user_id: 用户 ID
            job_id: 岗位 ID
            db: 数据库会话

        Returns:
            dict: {
                "match_score": int,
                "match_reasons": list[str],
                "match_risks": list[str],
                "resume_tips": list[{"original": str, "suggested": str}]
            }
        """
        # 1. 查缓存
        cached = await self._get_cached(user_id, job_id, db)
        if cached:
            logger.info("ai_explanation_cache_hit", user_id=str(user_id), job_id=job_id)
            return cached

        # 2. 获取用户简历和岗位信息
        resume_profile, resume_content = await self._get_user_resume(user_id, db)
        job = await self._get_job(job_id, db)

        if not job:
            return self._fallback_response("未找到该岗位")

        if not resume_profile:
            return self._fallback_response("请先上传简历以获得 AI 分析")

        # 3. 调用 LLM 生成解释
        explanation = await self._call_llm(resume_profile, resume_content, job)

        # 4. 存入缓存
        await self._save_cache(user_id, job_id, explanation, db)

        logger.info(
            "ai_explanation_generated",
            user_id=str(user_id),
            job_id=job_id,
            match_score=explanation.get("match_score"),
        )

        return explanation

    async def _get_cached(self, user_id, job_id: str, db: AsyncSession) -> dict | None:
        """从数据库读取缓存"""
        result = await db.execute(
            select(JobAIExplanation).where(
                JobAIExplanation.user_id == user_id,
                JobAIExplanation.job_id == job_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        return {
            "match_score": record.match_score,
            "match_reasons": record.match_reasons or [],
            "match_risks": record.match_risks or [],
            "resume_tips": record.resume_tips or [],
        }

    async def _get_user_resume(self, user_id, db: AsyncSession):
        """获取用户活跃简历的结构化摘要和完整内容"""
        result = await db.execute(
            select(Resume).where(
                Resume.user_id == user_id,
                Resume.active_status == True,
            ).limit(1)
        )
        resume = result.scalar_one_or_none()
        if not resume or not resume.extracted_content:
            return {}, {}

        profile = extract_resume_profile(resume.extracted_content)
        return profile, resume.extracted_content

    async def _get_job(self, job_id: str, db: AsyncSession) -> JobItem | None:
        """获取岗位详情"""
        result = await db.execute(
            select(JobItem).where(JobItem.id == job_id)
        )
        return result.scalar_one_or_none()

    async def _call_llm(
        self, resume_profile: dict, resume_content: dict, job: JobItem
    ) -> dict:
        """调用 LLM 生成结构化匹配分析"""
        # 构建简历信息
        skills = resume_profile.get("skills", [])
        work_exp = resume_content.get("work_experience", [])
        education = resume_content.get("education", [])

        skills_str = "、".join(skills) if skills else "未提供"

        # 最近工作经历（取前 2 段）
        work_lines = []
        for exp in work_exp[:2]:
            parts = []
            if exp.get("company"):
                parts.append(exp["company"])
            if exp.get("position") or exp.get("title"):
                parts.append(exp.get("position") or exp.get("title"))
            if exp.get("description"):
                parts.append(exp["description"][:200])
            if parts:
                work_lines.append("；".join(parts))
        work_str = "\n".join(work_lines) if work_lines else "未提供"

        # 教育背景（取前 2 段）
        edu_lines = []
        for edu in education[:2]:
            parts = []
            if edu.get("school"):
                parts.append(edu["school"])
            if edu.get("degree"):
                parts.append(edu["degree"])
            if edu.get("major"):
                parts.append(edu["major"])
            if parts:
                edu_lines.append("、".join(parts))
        edu_str = "\n".join(edu_lines) if edu_lines else "未提供"

        # 岗位描述（截取前 2000 字符）
        job_desc = (job.description or "")[:2000]

        system_prompt = """你是一个专业的求职顾问。请分析以下岗位描述与用户简历的匹配度。

请严格按以下 JSON 格式返回（不要添加任何其他文字、markdown 标记或解释）：
{"match_score": 85, "match_reasons": ["原因1", "原因2"], "match_risks": ["风险1"], "resume_tips": [{"original": "原文", "suggested": "建议改法"}]}

规则：
- match_score: 0-100 的整数，综合评估匹配程度
- match_reasons: 2-4 条匹配原因，每条简洁明了
- match_risks: 1-3 条差距或风险，每条简洁明了
- resume_tips: 0-3 条简历修改建议，每条包含 original（简历中的原文）和 suggested（建议的改法，要具体、可量化）
- 如果简历信息不足以分析，match_score 给 50，match_reasons 和 match_risks 给出合理推断
- 始终使用中文"""

        user_prompt = f"""【用户简历】
技能: {skills_str}
工作经历:
{work_str}
教育背景:
{edu_str}

【岗位描述】
{job_desc}

请分析匹配度并返回 JSON。"""

        try:
            response = await self.llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            # 解析 JSON（兼容 markdown code block）
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            result = json.loads(cleaned)

            # 校验并补充默认值
            return {
                "match_score": int(result.get("match_score", 50)),
                "match_reasons": result.get("match_reasons", []),
                "match_risks": result.get("match_risks", []),
                "resume_tips": result.get("resume_tips", []),
            }

        except Exception as e:
            logger.error("ai_explanation_llm_failed", error=str(e))
            return self._fallback_response(f"AI 分析暂时不可用: {str(e)}")

    async def _save_cache(
        self, user_id, job_id: str, explanation: dict, db: AsyncSession
    ) -> None:
        """将解释结果存入缓存（upsert）"""
        result = await db.execute(
            select(JobAIExplanation).where(
                JobAIExplanation.user_id == user_id,
                JobAIExplanation.job_id == job_id,
            )
        )
        record = result.scalar_one_or_none()

        if record:
            record.match_score = explanation["match_score"]
            record.match_reasons = explanation["match_reasons"]
            record.match_risks = explanation["match_risks"]
            record.resume_tips = explanation["resume_tips"]
        else:
            record = JobAIExplanation(
                user_id=user_id,
                job_id=job_id,
                match_score=explanation["match_score"],
                match_reasons=explanation["match_reasons"],
                match_risks=explanation["match_risks"],
                resume_tips=explanation["resume_tips"],
            )
            db.add(record)

        await db.commit()

    def _fallback_response(self, message: str) -> dict:
        """降级响应"""
        return {
            "match_score": 50,
            "match_reasons": [],
            "match_risks": [],
            "resume_tips": [],
            "fallback_message": message,
        }
