import os
import re
from typing import Any
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from functools import lru_cache
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger()

# ${VAR} 占位符匹配（api_key: ${LLM_DEEPSEEK_API_KEY}）
_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class _TolerantYamlSource(YamlConfigSettingsSource):
    """llm_providers.yaml 缺失/解析失败（如被误建为目录）时不阻塞启动，
    返回空配置走旧环境变量回退路径"""

    def _read_file(self, file_path):
        try:
            return super()._read_file(file_path)
        except Exception as e:
            logger.warning(
                "llm_yaml_config_load_failed",
                path=str(file_path),
                error=str(e),
            )
            return {}


def get_project_root() -> Path:
    """获取项目根目录"""
    # backend/app/config.py -> backend -> intelli-job
    return Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Intelli-Job API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database (PostgreSQL RDS)
    RDS_DRIVERNAME: str = "postgresql+asyncpg"
    RDS_USERNAME: str = "postgres"
    RDS_PASSWORD: str = "password"
    RDS_HOST: str = "localhost"
    RDS_PORT: int = 5432
    RDS_DB_NAME: str = "intellijob"
    
    # Construct DATABASE_URL from components
    @property
    def DATABASE_URL(self) -> str:
        return f"{self.RDS_DRIVERNAME}://{self.RDS_USERNAME}:{self.RDS_PASSWORD}@{self.RDS_HOST}:{self.RDS_PORT}/{self.RDS_DB_NAME}"

    # LangGraph Checkpointer（agent-context-overhaul Phase 1.1）
    # saver 需要 psycopg 3，与 SQLAlchemy 用的 asyncpg 是两个驱动：
    # 复用同一个 RDS 实例，但走独立 DSN 与独立连接池
    ENABLE_AGENT_CHECKPOINTER: bool = True
    CHECKPOINT_POOL_MAX_SIZE: int = 5
    # Agent 运行护栏（Phase 4.1）：之前依赖 langgraph 默认 25，多工具链路
    # （读记忆 → 搜索 → 解读 → 再搜索）容易碰顶后静默失败，显式落成配置便于调
    AGENT_RECURSION_LIMIT: int = 30

    @property
    def CHECKPOINTER_DSN(self) -> str:
        """psycopg 3 的 DSN：不能直接复用 DATABASE_URL（带 `+asyncpg` 方言前缀，saver 不认）

        用户名/密码做 URL 转义，避免密码里的特殊字符被当成分隔符
        """
        return (
            f"postgresql://{quote_plus(self.RDS_USERNAME)}:{quote_plus(self.RDS_PASSWORD)}"
            f"@{self.RDS_HOST}:{self.RDS_PORT}/{self.RDS_DB_NAME}"
        )
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PASSWORD: str = ""
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # LLM - Completion (DeepSeek)
    # YAML（llm_providers.yaml）存在时仅作 fallback 单供应商回退，见 effective_chat_providers
    LLM_COMPLETION_API_KEY: str
    LLM_COMPLETION_API_URL: str = "https://api.deepseek.com"
    LLM_COMPLETION_API_MODEL_NAME: str = "deepseek-chat"

    # LLM - Completion 多供应商 fallback（llm_providers.yaml 中以 ${VAR} 引用）
    LLM_DEEPSEEK_API_KEY: str = ""
    LLM_QWEN_API_KEY: str = ""      # 与 embedding 的 DashScope key 相同
    LLM_GLM_API_KEY: str = ""

    # Completion 供应商链（由 llm_providers.yaml 的 YAML 源填充）与请求超时
    completion_providers: list[dict[str, Any]] = []
    completion_timeout_seconds: int = 60
    # 供应商上下文上限兜底值：YAML 未声明 max_input_tokens 时采用。
    # SummarizationMiddleware 只有在模型暴露 max_input_tokens 时才会用 fraction 阈值，
    # 否则兜底 trigger=170000 tokens（远超 DeepSeek 上限，主动压缩形同关闭，见 D12）。
    # 取链上最弱 provider 的上限；填大了等于没改。
    LLM_COMPLETION_MAX_INPUT_TOKENS: int = 64000
    
    # LLM - Embedding (Qwen/Alibaba)
    LLM_EMBEDDING_API_KEY: str
    LLM_EMBEDDING_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_EMBEDDING_API_MODEL_NAME: str = "text-embedding-v4"
    
    # Zilliz Cloud (Vector DB)
    ZILLIZ_URI: str
    ZILLIZ_TOKEN: str
    ZILLIZ_JOB_ITEM_COLLECTION_NAME: str = "job_items"
    
    # Aliyun OSS (Object Storage for resumes)
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_ENDPOINT: str = "oss-cn-hangzhou.aliyuncs.com"
    OSS_BUCKET_NAME: str = "intellijob-resumes"
    
    # CORS
    CORS_ORIGINS: str = "*"  # 生产环境设置为具体域名，逗号分隔，如 "https://xxx.vercel.app,https://xxx.com"
    
    # Rate Limiting（api-abuse-protection：三档限流，值均经环境变量可调）
    RATE_LIMIT_PER_MINUTE: int = 30       # 通用档兜底
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5   # auth 档：login/register/refresh/forgot/reset
    RATE_LIMIT_AI_PER_MINUTE: int = 10    # AI 重接口档：chat 发消息 / jobs/match / 简历上传重解析

    # Abuse Protection（api-abuse-protection：资源天花板与用途治理）
    CHAT_MESSAGE_MAX_LENGTH: int = 5000   # 单条消息长度上限
    CHAT_DAILY_MESSAGE_LIMIT: int = 50    # 每用户每日消息配额（Redis 计数，按日滚动）
    REPARSE_HOURLY_LIMIT: int = 3         # 每份简历每小时重解析上限
    LOGIN_MAX_FAILURES: int = 5           # 登录失败锁定阈值（固定窗口，见 design.md 5.2）
    LOGIN_LOCKOUT_MINUTES: int = 15       # 登录锁定时长（分钟）
    RESUME_MAX_FILE_MB: int = 10          # 简历上传文件大小上限（MB）
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,  # 不区分大小写
        extra="ignore",  # 忽略额外的环境变量
        yaml_file="llm_providers.yaml",  # 文件不存在时 YAML 源自动忽略
        yaml_file_encoding="utf-8",  # Windows 默认 GBK 编码无法读 UTF-8 中文注释
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """接入 YAML 配置源，优先级低于环境变量 / .env"""
        yaml_settings = _TolerantYamlSource(settings_cls)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_settings,
            file_secret_settings,
        )

    @property
    def effective_chat_providers(self) -> list[dict[str, Any]]:
        """Completion 供应商链：YAML 优先，缺失/为空时回退 LLM_COMPLETION_API_* 单供应商。

        - ${VAR} 占位符在此展开：先查进程环境变量，再查 Settings 字段（.env 加载值）
        - 展开后 api_key 为空或缺必需字段的条目记 warning 并跳过
        """
        if self.completion_providers:
            providers: list[dict[str, Any]] = []
            for entry in self.completion_providers:
                name = str(entry.get("name", "")).strip()
                api_url = str(entry.get("api_url", "")).strip()
                model_name = str(entry.get("model_name", "")).strip()
                if not (name and api_url and model_name):
                    logger.warning(
                        "llm_provider_entry_invalid",
                        reason="missing name/api_url/model_name",
                        entry=str(entry),
                    )
                    continue
                api_key = self._expand_env_vars(str(entry.get("api_key", "")))
                if not api_key:
                    logger.warning(
                        "llm_provider_entry_skipped",
                        provider=name,
                        reason="api_key empty after ${VAR} expansion",
                    )
                    continue
                providers.append(
                    {
                        "name": name,
                        "api_url": api_url,
                        "model_name": model_name,
                        "api_key": api_key,
                        # 逐 provider 声明，未声明则用全局兜底值（供 D12 取链上最小值）
                        "max_input_tokens": int(entry["max_input_tokens"])
                        if entry.get("max_input_tokens")
                        else self.LLM_COMPLETION_MAX_INPUT_TOKENS,
                    }
                )
            if providers:
                return providers
            # YAML 存在但全部条目被过滤 → 继续走回退逻辑
            logger.warning(
                "llm_yaml_providers_all_filtered",
                reason="falling back to LLM_COMPLETION_API_*",
            )

        # 回退：旧环境变量组装单供应商（存量部署零改动）
        return [
            {
                "name": "deepseek",
                "api_url": self.LLM_COMPLETION_API_URL,
                "model_name": self.LLM_COMPLETION_API_MODEL_NAME,
                "api_key": self.LLM_COMPLETION_API_KEY,
                "max_input_tokens": self.LLM_COMPLETION_MAX_INPUT_TOKENS,
            }
        ]

    def _expand_env_vars(self, value: str) -> str:
        """将 ${VAR} 占位符展开为环境变量值（os.environ 优先，回退 Settings 字段）"""

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            resolved = os.environ.get(var_name)
            if resolved:
                return resolved
            # .env 加载的字段值不在 os.environ 中，从 Settings 实例取
            return str(getattr(self, var_name, "") or "")

        return _ENV_VAR_PATTERN.sub(_replace, value)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
