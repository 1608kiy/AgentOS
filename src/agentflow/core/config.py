"""配置管理系统"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """运行环境"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """LLM提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MIMO = "mimo"


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogFormat(str, Enum):
    """日志格式"""
    JSON = "json"
    CONSOLE = "console"


class LLMConfig(BaseSettings):
    """LLM配置"""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4o-mini"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60

    # OpenAI兼容端点（MiMo等第三方服务）
    openai_base_url: str = ""

    # Anthropic配置
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""

    # 本地LLM配置
    local_base_url: str = "http://localhost:11434"
    local_model: str = "llama3"

    model_config = {"env_prefix": "LLM_", "extra": "ignore"}


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    url: str = "sqlite:///./data/agentflow.db"

    model_config = {"env_prefix": "DATABASE_", "extra": "ignore"}


class RedisConfig(BaseSettings):
    """Redis配置"""
    url: str = "redis://localhost:6379"
    password: str = ""

    model_config = {"env_prefix": "REDIS_", "extra": "ignore"}


class AgentConfig(BaseSettings):
    """Agent配置"""
    max_iterations: int = 10
    timeout_seconds: int = 300
    default_model: str = "gpt-4o-mini"

    model_config = {"env_prefix": "AGENT_", "extra": "ignore"}


class VectorStoreConfig(BaseSettings):
    """向量存储配置"""
    store_type: str = "chroma"
    store_path: str = "./data/chroma"
    embedding_model: str = "text-embedding-3-small"

    model_config = {"env_prefix": "VECTOR_", "extra": "ignore"}


class APIConfig(BaseSettings):
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = "change-this-to-a-random-secret-key"

    model_config = {"env_prefix": "API_", "extra": "ignore"}


class LoggingConfig(BaseSettings):
    """日志配置"""
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON

    model_config = {"env_prefix": "LOG_", "extra": "ignore"}


# 项目根目录（src/agentflow/core/ → src/agentflow/ → project root）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class AgentFlowConfig(BaseSettings):
    """AgentFlow主配置"""
    app_name: str = "AgentFlow"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # 子配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = {"env_prefix": "", "env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: Any) -> Environment:
        if isinstance(v, str):
            return Environment(v)
        return v

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


def load_config(env_file: str | Path | None = None) -> AgentFlowConfig:
    """加载配置"""
    if env_file:
        return AgentFlowConfig(_env_file=env_file)
    return AgentFlowConfig()


def load_env_if_needed() -> None:
    """确保 .env 已加载到环境变量（供非 pydantic-settings 代码使用）"""
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE, override=False)
    except Exception:
        pass
