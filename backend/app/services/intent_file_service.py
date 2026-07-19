"""
Intent File Service - 使用 Markdown 文件存储用户意图

利用 deepagents 的 FilesystemMiddleware 让 Agent 自主管理 Intent 文件。
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.utils.logger import get_logger
from app.models.agent_memory import SearchIntent, SessionState, UserProfile, EventLog

logger = get_logger()


class IntentFileService:
    """管理服务 Intent Markdown 文件的读写"""
    
    def __init__(self, base_dir: str = None):
        """
        初始化 Intent 文件服务
        
        Args:
            base_dir: Intent 文件根目录，默认为项目内 workspace 目录（开发环境）
                  可通过 INTENT_WORKSPACE_DIR 环境变量覆盖
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        elif os.getenv('INTENT_WORKSPACE_DIR'):
            # ✅ 优先使用环境变量（本地测试时由 run_local.py 设置）
            self.base_dir = Path(os.getenv('INTENT_WORKSPACE_DIR'))
        else:
            # 默认路径：优先使用项目内的 workspace 目录（开发环境）
            project_workspace = Path(__file__).parent.parent.parent / 'workspace'
            if project_workspace.exists():
                self.base_dir = project_workspace
            elif os.getenv("ENVIRONMENT") == "prod":
                self.base_dir = Path("/opt/intelli-job/data/intents")
            else:
                self.base_dir = Path.home() / ".intelli-job" / "intents"
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("intent_file_service_initialized", base_dir=str(self.base_dir))
    
    def get_session_dir(self, user_id: str, thread_id: str) -> Path:
        """
        获取 Session 目录路径
        
        文件组织结构：
        {base_dir}/
        └── user-{user_id}/
            └── session-{thread_id}/
                ├── session.md
                ├── search_intent.json
                ├── profile.md
                └── events.jsonl
        """
        user_dir = self.base_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        session_dir = user_dir / f"session-{thread_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def get_intent_path(self, user_id: str, thread_id: str) -> Path:
        """兼容旧接口，指向 session.md"""
        return self.get_session_dir(user_id, thread_id) / "session.md"
    
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
    
    # --- Profile Management ---

    def initialize_profile(self, user_id: str, resume_data: Dict[str, Any]) -> Path:
        """
        从简历解析结果初始化 profile.md
        """
        # 简化实现：直接根据用户 ID 查找或创建主 Profile 文件
        # 实际生产中可能需要更复杂的版本管理
        user_dir = self.base_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        profile_path = user_dir / "profile.md"

        content = [
            "# User Profile",
            "",
            "##  Facts (From Active Resume)",
        ]
        
        # 提取简历关键信息
        # 1. 当前职位/最新工作经历
        work_exp = resume_data.get('work_experience', [])
        if work_exp and isinstance(work_exp, list) and len(work_exp) > 0:
            latest_job = work_exp[0]
            if isinstance(latest_job, dict):
                title = latest_job.get('title') or latest_job.get('position')
                company = latest_job.get('company')
                if title:
                    content.append(f"- **current_title**: {title}")
                    if company:
                        content[-1] += f" @ {company}"
        
        # 2. 最高学历
        education = resume_data.get('education', [])
        if education and isinstance(education, list) and len(education) > 0:
            highest_edu = education[0]  # 假设第一个是最高学历
            if isinstance(highest_edu, dict):
                school = highest_edu.get('school')
                degree = highest_edu.get('degree')
                major = highest_edu.get('major')
                edu_str = []
                if school:
                    edu_str.append(school)
                if degree:
                    edu_str.append(degree)
                if major:
                    edu_str.append(major)
                if edu_str:
                    content.append(f"- **education_level**: {' - '.join(edu_str)}")
        
        # 3. 技能列表
        skills = resume_data.get('skills', [])
        if skills and isinstance(skills, list) and len(skills) > 0:
            content.append(f"- **skills**: {', '.join(skills[:10])}")  # 只取前10个技能

        content.extend([
            "",
            "## 🎯 Confirmed Long-Term Preferences",
            "- (待用户确认)",
            "",
            "## 🚫 Negative Signals",
            "- (暂无)",
            "",
            f"## 📅 Last Updated\n{datetime.utcnow().isoformat()}",
        ])

        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
            logger.info("profile_initialized", path=str(profile_path), user_id=user_id)
        except Exception as e:
            logger.error("profile_init_failed", error=str(e))
        
        return profile_path

    def append_event(self, user_id: str, thread_id: str, event: EventLog):
        """
        追加事件到 events.jsonl
        """
        session_dir = self.get_session_dir(user_id, thread_id)
        events_path = session_dir / "events.jsonl"
        
        try:
            with open(events_path, 'a', encoding='utf-8') as f:
                f.write(event.model_dump_json() + '\n')
        except Exception as e:
            logger.error("event_append_failed", error=str(e))

    def update_search_intent(self, user_id: str, thread_id: str, updates: Dict[str, Any]):
        """
        增量更新 search_intent.json
        """
        session_dir = self.get_session_dir(user_id, thread_id)
        intent_path = session_dir / "search_intent.json"
        
        current_intent = {}
        if intent_path.exists():
            try:
                with open(intent_path, 'r', encoding='utf-8') as f:
                    current_intent = json.load(f)
            except:
                pass

        # 深度合并（这里做简单覆盖）
        current_intent.update(updates)
        current_intent['updated_at'] = datetime.utcnow().isoformat()

        try:
            with open(intent_path, 'w', encoding='utf-8') as f:
                json.dump(current_intent, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("intent_update_failed", error=str(e))
