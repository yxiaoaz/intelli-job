from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


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
    LLM_COMPLETION_API_KEY: str
    LLM_COMPLETION_API_URL: str = "https://api.deepseek.com"
    LLM_COMPLETION_API_MODEL_NAME: str = "deepseek-chat"
    
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
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,  # 不区分大小写
        extra="ignore"  # 忽略额外的环境变量
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
