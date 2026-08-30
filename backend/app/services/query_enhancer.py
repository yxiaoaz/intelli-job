import json
from typing import Any
from app.utils.logger import get_logger

logger = get_logger()


def extract_resume_profile(extracted_content: dict) -> dict[str, Any]:
    """从 resume.extracted_content 提取关键信息，供 QueryEnhancer 和 API 层共用。
    
    与 conversation_agent 中 get_user_profile tool 的逻辑对齐。
    """
    if not extracted_content:
        return {}
    
    profile: dict[str, Any] = {}
    
    # 技能
    skills = extracted_content.get("skills")
    if skills:
        if isinstance(skills, list):
            profile["skills"] = skills[:10]
        elif isinstance(skills, str):
            profile["skills"] = [s.strip() for s in skills.split(",") if s.strip()][:10]
    
    # 最近工作经历
    work_exp = extracted_content.get("work_experience")
    if work_exp and isinstance(work_exp, list) and len(work_exp) > 0:
        latest = work_exp[0]
        if latest.get("company"):
            profile["latest_company"] = latest["company"]
        # 解析 schema 中 work_experience 的职位字段是 position，兼容旧数据的 title
        position = latest.get("position") or latest.get("title")
        if position:
            profile["latest_title"] = position
    
    # 最高学历
    education = extracted_content.get("education")
    if education and isinstance(education, list) and len(education) > 0:
        latest_edu = education[0]
        if latest_edu.get("school"):
            profile["school"] = latest_edu["school"]
        if latest_edu.get("degree"):
            profile["degree"] = latest_edu["degree"]
    
    return profile
