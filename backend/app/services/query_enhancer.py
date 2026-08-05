import json
from typing import Any
from langchain_openai import ChatOpenAI
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
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
        if latest.get("title"):
            profile["latest_title"] = latest["title"]
    
    # 最高学历
    education = extracted_content.get("education")
    if education and isinstance(education, list) and len(education) > 0:
        latest_edu = education[0]
        if latest_edu.get("school"):
            profile["school"] = latest_edu["school"]
        if latest_edu.get("degree"):
            profile["degree"] = latest_edu["degree"]
    
    return profile


class QueryEnhancer:
    """LLM 关键词增强服务 — 独立于 JobMatchingService，由调用方决定是否启用。"""
    
    # 类变量：所有实例共享同一份缓存，避免每次请求重建导致缓存失效
    _shared_cache: dict[str, dict] = {}
    
    def __init__(self):
        # 低 temperature，确保输出稳定、确定性强
        self._model = ChatOpenAI(
            model=settings.LLM_COMPLETION_API_MODEL_NAME,
            temperature=0.3,
            api_key=settings.LLM_COMPLETION_API_KEY,
            base_url=settings.LLM_COMPLETION_API_URL,
        )
    
    async def enhance(
        self,
        keywords: str,
        resume_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """对用户关键词进行 LLM 扩写，返回结构化增强结果。
        
        Returns:
            {
                "expanded_query": "产品经理 B端产品经理 PM 产品策划",
                "synonyms": ["B端产品经理", "PM", "产品策划"],
                "category": "产品",
                "original_keywords": "产品经理"
            }
        """
        # 缓存命中（使用类变量共享缓存）
        cache_key = self._build_cache_key(keywords, resume_profile)
        if cache_key in self._shared_cache:
            logger.info("query_enhancer_cache_hit", keywords=keywords)
            return self._shared_cache[cache_key]
        
        # 构建 prompt
        messages = self._build_messages(keywords, resume_profile)
        
        try:
            logger.info("query_enhancer_start", keywords=keywords, has_resume=resume_profile is not None)
            response = await self._model.ainvoke(messages)
            raw = response.content.strip()
            
            # 解析 JSON（兼容 markdown code block）
            if raw.startswith("```"):
                # 去掉 ```json ... ```
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            
            parsed = json.loads(raw)
            result = {
                "expanded_query": parsed.get("expanded_query", keywords),
                "synonyms": parsed.get("synonyms", []),
                "category": parsed.get("category", ""),
                "original_keywords": keywords,
            }
            
            # 写入类变量缓存
            self._shared_cache[cache_key] = result
            logger.info("query_enhancer_success", keywords=keywords, expanded=result["expanded_query"][:100])
            return result
            
        except Exception as e:
            # 降级：返回原始关键词
            logger.warning("query_enhancer_failed", keywords=keywords, error=str(e))
            return {
                "expanded_query": keywords,
                "synonyms": [],
                "category": "",
                "original_keywords": keywords,
            }
    
    def _build_cache_key(self, keywords: str, resume_profile: dict | None) -> str:
        """构建缓存 key，关键词 + 简历摘要"""
        base = keywords.strip().lower()
        if resume_profile:
            # 用 skills 做简单指纹，避免整个 dict 序列化
            skills = resume_profile.get("skills", [])
            skills_key = ",".join(skills[:5]) if skills else ""
            return f"{base}|{skills_key}"
        return base
    
    def _build_messages(
        self,
        keywords: str,
        resume_profile: dict[str, Any] | None,
    ) -> list[dict]:
        system_prompt = (
            "你是一个职位搜索关键词增强助手。\n"
            "用户会输入搜索关键词，你需要：\n"
            "1. 扩展出 3-5 个相关的同义词或子关键词（更精准、更具体）\n"
            "2. 判断所属职位类别\n"
            "3. 生成一段用于向量搜索的扩展查询文本\n\n"
            "如果提供了用户简历信息，请结合其背景做个性化扩展（例如有 B 端经验的用户搜'产品经理'，"
            "扩展词应偏向'B端产品经理'）。\n\n"
            "严格以 JSON 格式返回，不要包含任何其他文字：\n"
            '{"expanded_query": "扩展后的搜索文本，空格分隔", '
            '"synonyms": ["同义词1", "同义词2", "同义词3"], '
            '"category": "职位类别"}'
        )
        
        user_content = f"搜索关键词：{keywords}"
        if resume_profile:
            resume_parts = []
            if resume_profile.get("skills"):
                resume_parts.append(f"技能: {', '.join(resume_profile['skills'][:8])}")
            if resume_profile.get("latest_company"):
                resume_parts.append(f"最近职位: {resume_profile.get('latest_title', '')} @ {resume_profile['latest_company']}")
            if resume_profile.get("degree"):
                resume_parts.append(f"学历: {resume_profile['degree']}")
            if resume_parts:
                user_content += "\n\n用户简历摘要：\n" + "\n".join(resume_parts)
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
