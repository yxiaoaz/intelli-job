"""PreferenceExtractionService — 从简历内容抽取求职偏好。

调 LLM 独立 prompt（与简历解析分离），输出 JobPreference。
失败不阻塞主流程（warning log）。
"""
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

import yaml
from langchain_core.messages import SystemMessage, HumanMessage

from app.memory.schemas import JobPreference, SalaryRange
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

logger = get_logger()

# 加载 prompt 模板
_PROMPT_PATH = Path(__file__).parent / "prompts" / "preference_extraction.yaml"


def _load_prompt() -> dict:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class PreferenceExtractionService:
    """从简历解析结果抽取求职偏好"""

    def __init__(self):
        self.llm_service = LLMService()
        self.prompt = _load_prompt()

    async def extract(
        self,
        resume_extracted: dict,
        resume_id: UUID,
        user_id: UUID,
    ) -> Optional[JobPreference]:
        """调 LLM 抽求职偏好。

        Args:
            resume_extracted: 简历解析结果 dict（来自 ResumeParserService）
            resume_id: 简历 ID
            user_id: 用户 ID

        Returns:
            JobPreference 或 None（失败时）
        """
        try:
            # 构造 resume 文本摘要
            resume_text = self._summarize_resume(resume_extracted)
            if not resume_text.strip():
                logger.warning("preference_extraction_empty_resume", resume_id=str(resume_id))
                return None

            # 构造 prompt
            system_msg = self.prompt["system"]
            user_msg = self.prompt["user"].format(resume_content=resume_text)

            # 调 LLM
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]

            response = await self.llm_service.generate_completion(messages)

            # 解析 JSON
            pref_data = self._parse_response(response)
            if not pref_data:
                return None

            # 构造 JobPreference
            return self._build_preference(pref_data)

        except Exception as e:
            logger.warning(
                "preference_extraction_failed",
                resume_id=str(resume_id),
                user_id=str(user_id),
                error=str(e),
            )
            return None

    def _summarize_resume(self, data: dict) -> str:
        """将简历解析结果转为可读文本"""
        parts = []

        # 基本信息
        info = data.get("personal_info", {})
        if info:
            info_line = "、".join(f"{k}: {v}" for k, v in info.items() if v)
            if info_line:
                parts.append(f"基本信息：{info_line}")

        # 教育
        edu = data.get("education", [])
        if edu:
            for e in edu[:3]:
                parts.append(
                    f"教育：{e.get('school', '')} {e.get('degree', '')} "
                    f"{e.get('major', '')} {e.get('start_date', '')}-{e.get('end_date', '')}"
                )

        # 工作
        work = data.get("work_experience", [])
        if work:
            for w in work[:3]:
                parts.append(
                    f"工作：{w.get('company', '')} {w.get('title', '')} "
                    f"{w.get('start_date', '')}-{w.get('end_date', '')}"
                )

        # 技能
        skills = data.get("skills", [])
        if skills:
            parts.append(f"技能：{', '.join(skills[:15])}")

        # 项目
        projects = data.get("projects", [])
        if projects:
            for p in projects[:2]:
                parts.append(f"项目：{p.get('name', '')} - {p.get('description', '')[:100]}")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> Optional[dict]:
        """从 LLM 响应解析 JSON"""
        text = response.strip()

        # 去掉可能的 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("preference_extraction_json_parse_failed", response_preview=text[:200])
            return None

    def _build_preference(self, data: dict) -> JobPreference:
        """从 dict 构造 JobPreference（容错）"""
        # salary 处理
        salary_data = data.get("salary")
        salary = None
        if salary_data and isinstance(salary_data, dict):
            salary_min = salary_data.get("min")
            if salary_min is not None:
                salary = SalaryRange(
                    min=int(salary_min),
                    max=salary_data.get("max"),
                    currency=salary_data.get("currency", "CNY"),
                )

        # recruitment_types 过滤为合法 Literal
        valid_types = {"INTERN", "GRADUATE", "EXPERIENCED"}
        raw_types = data.get("recruitment_types", [])
        filtered_types = [t for t in raw_types if t in valid_types]

        return JobPreference(
            target_roles=data.get("target_roles", []),
            locations=data.get("locations", []),
            salary=salary,
            recruitment_types=filtered_types,
            industries=data.get("industries", []),
            skills=data.get("skills", []),
            target_companies=data.get("target_companies", []),
            target_company_types=data.get("target_company_types", []),
        )
