"""
Intent File Service — 文件目录管理。

职责：提供 base_dir 路径解析（环境变量 / 默认路径）。
记忆读写统一走 app.memory.service.MemoryService。
"""

import os
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger()


class IntentFileService:
    """管理记忆文件根目录"""

    def __init__(self, base_dir: str = None):
        """
        初始化文件服务

        Args:
            base_dir: 文件根目录，默认为项目内 workspace 目录（开发环境）
                  可通过 INTENT_WORKSPACE_DIR 环境变量覆盖
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        elif os.getenv('INTENT_WORKSPACE_DIR'):
            self.base_dir = Path(os.getenv('INTENT_WORKSPACE_DIR'))
        else:
            project_workspace = Path(__file__).parent.parent.parent / 'workspace'
            if project_workspace.exists():
                self.base_dir = project_workspace
            elif os.getenv("ENVIRONMENT") == "prod":
                self.base_dir = Path("/opt/intelli-job/data/intents")
            else:
                self.base_dir = Path.home() / ".intelli-job" / "intents"

        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("intent_file_service_initialized", base_dir=str(self.base_dir))

