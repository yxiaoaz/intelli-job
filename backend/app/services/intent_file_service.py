"""
Intent File Service - 使用 Markdown 文件存储用户意图

利用 deepagents 的 FilesystemMiddleware 让 Agent 自主管理 Intent 文件。
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from app.utils.logger import get_logger

logger = get_logger()


class IntentFileService:
    """管理服务 Intent Markdown 文件的读写"""
    
    def __init__(self, base_dir: str = None):
        """
        初始化 Intent 文件服务
        
        Args:
            base_dir: Intent 文件根目录，默认为 ~/.intelli-job/intents
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # 默认路径：dev 环境用家目录，prod 环境用 /opt
            if os.getenv("ENVIRONMENT") == "prod":
                self.base_dir = Path("/opt/intelli-job/data/intents")
            else:
                self.base_dir = Path.home() / ".intelli-job" / "intents"
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("intent_file_service_initialized", base_dir=str(self.base_dir))
    
    def get_intent_path(self, user_id: str, thread_id: str) -> Path:
        """
        获取 Intent 文件路径
        
        文件组织结构：
        {base_dir}/
        └── user-{user_id}/
            └── session-{thread_id}.md
        """
        user_dir = self.base_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / f"session-{thread_id}.md"
    
    def format_intent_to_markdown(self, intent_data: Dict[str, Any]) -> str:
        """
        将 Intent 数据格式化为 Markdown
        
        格式示例：
        ```markdown
        # Session Intent
        
        ## Metadata
        thread_id: abc-123
        user_id: user-456
        created_at: 2026-01-15T10:30:00Z
        updated_at: 2026-01-15T14:20:00Z
        
        ## Preferences
        preferred_city: 深圳, 北京
        preferred_job_titles: 产品经理, AI 产品经理
        salary_min: 20000
        salary_max: 30000
        salary_currency: CNY
        skills: Python, React, NLP
        search_direction: AI 产品方向
        include_resume: true
        resume_id: resume-789
        
        ## Reasoning
        用户在第 3 轮对话中明确表示...
        ```
        """
        lines = [
            "# Session Intent",
            "",
            "## Metadata",
            f"thread_id: {intent_data.get('thread_id', '')}",
            f"user_id: {intent_data.get('user_id', '')}",
            f"created_at: {intent_data.get('created_at', datetime.utcnow().isoformat())}",
            f"updated_at: {datetime.utcnow().isoformat()}",
            "",
            "## Preferences",
        ]
        
        # 列表字段（逗号分隔）
        for key in ['preferred_city', 'preferred_job_titles', 'skills']:
            values = intent_data.get(key, [])
            if isinstance(values, list) and values:
                lines.append(f"{key}: {', '.join(str(v) for v in values)}")
            elif values:
                lines.append(f"{key}: {values}")
        
        # 标量字段
        for key in ['search_direction', 'resume_id', 'education_level']:
            value = intent_data.get(key)
            if value:
                lines.append(f"{key}: {value}")
        
        # 工作经验
        work_exp = intent_data.get('work_experience_years')
        if work_exp is not None:
            lines.append(f"work_experience_years: {work_exp}")
        
        # 薪资期望
        salary = intent_data.get('salary_expectation')
        if salary and isinstance(salary, dict):
            lines.append(f"salary_min: {salary.get('min', 0)}")
            lines.append(f"salary_max: {salary.get('max', 0)}")
            lines.append(f"salary_currency: {salary.get('currency', 'CNY')}")
        
        # 布尔字段
        include_resume = intent_data.get('include_resume_in_search', True)
        lines.append(f"include_resume: {str(include_resume).lower()}")
        
        # 推理过程
        reasoning = intent_data.get('reasoning')
        if reasoning:
            lines.extend([
                "",
                "## Reasoning",
                reasoning,
            ])
        
        return '\n'.join(lines)
    
    def parse_intent_from_markdown(self, content: str) -> Dict[str, Any]:
        """
        从 Markdown 解析 Intent 数据
        
        支持简单的 key: value 格式，自动处理类型转换
        """
        intent = {}
        current_section = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # 检测章节标题
            if line.startswith('## '):
                current_section = line[3:].strip().lower()
                continue
            
            # 检测 key: value 格式
            if ':' in line and current_section:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if not value:
                    continue
                
                # 根据 section 和 key 做类型转换
                if current_section == 'metadata':
                    if key in ['created_at', 'updated_at']:
                        try:
                            intent[key] = datetime.fromisoformat(value)
                        except:
                            intent[key] = value
                    else:
                        intent[key] = value
                
                elif current_section == 'preferences':
                    # 列表字段
                    if key in ['preferred_city', 'preferred_job_titles', 'skills']:
                        intent[key] = [v.strip() for v in value.split(',') if v.strip()]
                    
                    # 数字字段
                    elif key in ['salary_min', 'salary_max', 'work_experience_years']:
                        try:
                            intent[key] = int(value)
                        except:
                            intent[key] = 0
                    
                    # 布尔字段
                    elif key == 'include_resume':
                        intent[key] = value.lower() == 'true'
                    
                    # 其他字段
                    else:
                        intent[key] = value
                
                elif current_section == 'reasoning':
                    intent['reasoning'] = value
        
        return intent
    
    def save_intent(self, user_id: str, thread_id: str, intent_data: Dict[str, Any]) -> Path:
        """
        保存 Intent 到 Markdown 文件（原子写入）
        
        Args:
            user_id: 用户 ID
            thread_id: 会话线程 ID
            intent_data: Intent 数据字典
        
        Returns:
            文件路径
        """
        file_path = self.get_intent_path(user_id, thread_id)
        
        # 格式化内容
        content = self.format_intent_to_markdown(intent_data)
        
        # 原子写入：先写临时文件，再重命名
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            temp_path.rename(file_path)
            logger.info("intent_saved", path=str(file_path), user_id=user_id, thread_id=thread_id)
        except Exception as e:
            logger.error("intent_save_failed", error=str(e), path=str(file_path))
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()
            raise
        
        return file_path
    
    def load_intent(self, user_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        从 Markdown 文件加载 Intent
        
        Args:
            user_id: 用户 ID
            thread_id: 会话线程 ID
        
        Returns:
            Intent 数据字典，如果文件不存在则返回 None
        """
        file_path = self.get_intent_path(user_id, thread_id)
        
        if not file_path.exists():
            logger.debug("intent_file_not_found", path=str(file_path))
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            intent = self.parse_intent_from_markdown(content)
            logger.info("intent_loaded", path=str(file_path), user_id=user_id, thread_id=thread_id)
            return intent
        except Exception as e:
            logger.error("intent_load_failed", error=str(e), path=str(file_path))
            return None
    
    def delete_intent(self, user_id: str, thread_id: str) -> bool:
        """
        删除 Intent 文件
        
        Args:
            user_id: 用户 ID
            thread_id: 会话线程 ID
        
        Returns:
            是否成功删除
        """
        file_path = self.get_intent_path(user_id, thread_id)
        
        if not file_path.exists():
            return False
        
        try:
            file_path.unlink()
            logger.info("intent_deleted", path=str(file_path), user_id=user_id, thread_id=thread_id)
            return True
        except Exception as e:
            logger.error("intent_delete_failed", error=str(e), path=str(file_path))
            return False
    
    def list_user_intents(self, user_id: str) -> list[Path]:
        """
        列出用户的所有 Intent 文件
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Intent 文件路径列表
        """
        user_dir = self.base_dir / f"user-{user_id}"
        
        if not user_dir.exists():
            return []
        
        return sorted(user_dir.glob("session-*.md"))
