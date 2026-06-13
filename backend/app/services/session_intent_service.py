"""Session Intent Service - 意图提取与管理服务"""

import logging
import json
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

logger = logging.getLogger(__name__)


class SalaryExpectation(BaseModel):
    """薪资期望"""
    min: int = Field(description="最低薪资（元/月）", ge=0)
    max: int = Field(description="最高薪资（元/月）", ge=0)
    currency: str = Field(default="CNY", description="货币单位")


class IntentExtractionResult(BaseModel):
    """从对话中提取的用户意图"""
    
    # 用户表达的求职偏好
    preferred_city: Optional[list[str]] = Field(
        default=None,
        description="意向城市列表。如果用户未提及则为 null"
    )
    preferred_job_titles: Optional[list[str]] = Field(
        default=None,
        description="意向岗位名称列表。例如：['算法工程师', 'AI产品经理']"
    )
    salary_expectation: Optional[SalaryExpectation] = Field(
        default=None,
        description="薪资期望范围"
    )
    skills: Optional[list[str]] = Field(
        default=None,
        description="用户提到的技能。通常从简历继承，用户可补充"
    )
    search_direction: Optional[str] = Field(
        default=None,
        description="当前求职方向标签。用于区分不同方向，如'AI算法'、'产品经理'"
    )
    
    # 行为判断
    should_search_now: bool = Field(
        description="是否应该立即执行搜索",
        examples=[True, False]
    )
    search_keywords: Optional[str] = Field(
        default=None,
        description="如果 should_search_now=true，生成搜索关键词"
    )
    
    # 推理过程（用于调试）
    reasoning: Optional[str] = Field(
        default=None,
        description="AI 的推理过程，解释为什么做出这些判断"
    )


class SearchQueryBuilder:
    """构建语义搜索的 Query"""
    
    @staticmethod
    def build_semantic_query(
        intent: dict,
        user_message: str,
        include_resume: bool = True
    ) -> dict:
        """
        构建分层 Query，平衡精准度和召回率
        
        Args:
            intent: SessionIntent 字典
            user_message: 用户当前消息
            include_resume: 是否包含简历信息
            
        Returns:
            {
                "semantic_query": "...",  # 用于向量搜索
                "hard_filters": {...},     # 用于硬过滤
                "resume_profile": {...}    # 用于匹配度计算
            }
        """
        
        # === 第1层：核心语义（必须包含）===
        semantic_parts = []
        
        # 1.1 用户当前消息（最高优先级）
        if user_message:
            semantic_parts.append(user_message)
        
        # 1.2 目标岗位（从 intent 提取）
        if intent.get("preferred_job_titles"):
            # 取最近的方向，或者第一个
            direction = intent.get("search_direction") or intent["preferred_job_titles"][0]
            semantic_parts.append(f"岗位：{direction}")
        
        # 1.3 关键技能（从简历或 intent 提取）
        skills = intent.get("skills") or []
        if skills:
            # 只取前5个核心技能，避免噪声
            semantic_parts.append(f"技能：{', '.join(skills[:5])}")
        
        # === 第2层：硬过滤（不参与向量搜索，但用于后过滤）===
        hard_filters = {}
        
        # 2.1 城市（如果有明确意向）
        if intent.get("preferred_city"):
            hard_filters["location"] = intent["preferred_city"]
        
        # 2.2 薪资范围（如果用户明确提及）
        if intent.get("salary_expectation"):
            hard_filters["salary_min"] = intent["salary_expectation"]["min"]
            hard_filters["salary_max"] = intent["salary_expectation"]["max"]
        
        return {
            "semantic_query": " ".join(semantic_parts),
            "hard_filters": hard_filters,
        }


class SessionIntentService:
    """Session 意图管理服务"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
    async def extract_intent_from_message(
        self,
        user_message: str,
        current_intent: dict,
        user_profile_summary: str = ""
    ) -> IntentExtractionResult:
        """从用户消息中提取结构化意图
        
        Args:
            user_message: 用户当前消息
            current_intent: 当前已知的意图（JSON dict）
            user_profile_summary: 用户简历摘要
            
        Returns:
            IntentExtractionResult - 结构化的意图提取结果
        """
        try:
            # 创建 Agent with Structured Output
            agent = create_agent(
                model=self.llm_service.chat_model,
                tools=[],  # 不需要工具，只做信息提取
                response_format=ToolStrategy(IntentExtractionResult),
                system_prompt=self._build_extraction_prompt()
            )
            
            # 调用 Agent
            result = await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": self._build_user_prompt(
                        user_message, 
                        current_intent, 
                        user_profile_summary
                    )
                }]
            })
            
            # 获取结构化响应
            structured_response = result.get("structured_response")
            if not structured_response:
                logger.warning("extract_intent_no_structured_response")
                return self._fallback_result()
            
            return structured_response
            
        except ValidationError as e:
            logger.error(f"extract_intent_validation_error: {e}")
            return self._fallback_result()
        except Exception as e:
            logger.error(f"extract_intent_failed: {e}")
            return self._fallback_result()
    
    def _build_extraction_prompt(self) -> str:
        """构建意图提取的系统 Prompt"""
        return """你是一个专业的求职顾问助手。你的任务是从用户对话中提取结构化的求职意向。

【核心规则】
1. **只提取明确表达的信息**：如果用户没说某个字段，返回 null
2. **智能合并策略**（重要）：
   - **追加场景**：用户说"也"、"或者"、"还有" → 追加新值
     示例："我想去北京或深圳" → preferred_city: ["北京", "深圳"]
   - **替换场景**：用户说"算了"、"还是"、"改成"、"不看XX了" → 替换旧值
     示例："算了，还是找深圳吧" → preferred_city: ["深圳"]（删除"北京"）
   - **默认行为**：如果无法判断，优先替换（避免列表无限增长）
3. **方向切换检测**：如果用户说"算了"、"还是看XX吧"，更新 search_direction
4. **搜索决策**：
   - 如果用户提到具体岗位关键词 → should_search_now=true
   - 如果信息严重不足（如无岗位、无地点）→ should_search_now=false
   - 如果用户表现出不耐烦（如"随便"、"你看着办"）→ should_search_now=true，基于已有信息搜索

【信息继承原则】
- 用户未提及城市 → 从 current_intent.preferred_city 继承（选第一个）
- 用户未提及岗位 → 不要猜测，保持 null
- 用户说"算了"、"再看看" → 不要追问，设置 should_search_now=true

【输出格式】
必须返回 IntentExtractionResult 格式的 JSON，包含以下字段：
- preferred_city: 城市列表（null 或 ["深圳"]）
- preferred_job_titles: 岗位列表（null 或 ["算法工程师"]）
- salary_expectation: 薪资对象（null 或 {"min": 15000, "max": 25000}）
- search_direction: 方向标签（null 或 "AI算法"）
- should_search_now: true/false
- search_keywords: 搜索关键词字符串（如果需要搜索）
- reasoning: 你的推理过程（说明是追加还是替换，以及原因）

示例1（追加）：
用户："我想去北京或深圳找算法工作"
→ {
  "preferred_city": ["北京", "深圳"],
  "preferred_job_titles": ["算法工程师"],
  "search_direction": "AI算法",
  "should_search_now": true,
  "search_keywords": "算法工程师 AI",
  "reasoning": "用户表达了多个城市偏好，使用追加策略"
}

示例2（替换）：
用户："算了，还是看深圳的产品经理吧"
→ {
  "preferred_city": ["深圳"],
  "preferred_job_titles": ["产品经理"],
  "search_direction": "产品经理",
  "should_search_now": true,
  "search_keywords": "产品经理",
  "reasoning": "用户用'算了'表示替换，删除之前的城市和岗位"
}

示例3（信息不足）：
用户："找工作"
→ {
  "preferred_city": null,
  "preferred_job_titles": null,
  "should_search_now": false,
  "search_keywords": null,
  "reasoning": "信息严重不足，需要澄清"
}"""
    
    def _build_user_prompt(
        self,
        user_message: str,
        current_intent: dict,
        user_profile_summary: str
    ) -> str:
        """构建用户 Prompt"""
        prompt_parts = [
            f"用户消息：{user_message}",
            f"\n当前已知信息：{json.dumps(current_intent, ensure_ascii=False)}",
        ]
        
        if user_profile_summary:
            prompt_parts.append(f"\n用户简历摘要：{user_profile_summary}")
        
        prompt_parts.append("\n请提取用户的求职意向。")
        
        return "\n".join(prompt_parts)
    
    def _fallback_result(self) -> IntentExtractionResult:
        """降级结果（当 LLM 失败时）"""
        return IntentExtractionResult(
            should_search_now=False,
            reasoning="LLM 提取失败，使用降级策略"
        )
