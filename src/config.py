import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Multi-Agent AI Platform"
    API_ENVIRONMENT: str = os.getenv("API_ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", 8000))
    API_LOG_LEVEL: str = os.getenv("API_LOG_LEVEL", "INFO")
    # Echo every SQL statement to stdout — opt-in only; it drowns real logs
    LOG_SQL: bool = os.getenv("LOG_SQL", "false").lower() == "true"

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "multi_agent_ai")

    @property
    def DATABASE_URL(self) -> str:
        # "+psycopg" selects psycopg3 (the driver declared in pyproject.toml).
        # psycopg3 supports both sync and async, so the same URL scheme works
        # for get_db_engine() (sync) and get_async_engine() (async) below.
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TOPIC_PREFIX: str = os.getenv("KAFKA_TOPIC_PREFIX", "multi_agent")

    @property
    def KAFKA_TOPICS(self) -> dict:
        return {
            "agent_started": f"{self.KAFKA_TOPIC_PREFIX}.agent.started",
            "agent_completed": f"{self.KAFKA_TOPIC_PREFIX}.agent.completed",
            "agent_failed": f"{self.KAFKA_TOPIC_PREFIX}.agent.failed",
            "agent_progress": f"{self.KAFKA_TOPIC_PREFIX}.agent.progress",
            "workflow_completed": f"{self.KAFKA_TOPIC_PREFIX}.workflow.completed",
        }

    # Temporal
    TEMPORAL_HOST: str = os.getenv("TEMPORAL_HOST", "localhost")
    TEMPORAL_PORT: int = int(os.getenv("TEMPORAL_PORT", 7233))
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    TEMPORAL_TASK_QUEUE: str = os.getenv("TEMPORAL_TASK_QUEUE", "ai_agents")

    # LLM
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # LiteLLM
    # Note: field name deliberately does NOT match the LITELLM_LOG env var —
    # litellm itself reads LITELLM_LOG directly from the process environment
    # (via its own dotenv auto-load) as a Python logging level name (e.g.
    # "INFO"), so this app-level verbosity toggle must use a different name
    # to avoid pydantic trying to coerce that same string into a bool.
    LITELLM_VERBOSE: bool = os.getenv("LITELLM_VERBOSE", "false").lower() == "true"
    LITELLM_CACHE: bool = os.getenv("LITELLM_CACHE", "false").lower() == "true"

    # Observability - Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    # Feature Flags
    ENABLE_APPROVAL_WORKFLOW: bool = os.getenv("ENABLE_APPROVAL_WORKFLOW", "true").lower() == "true"
    ENABLE_KAFKA_OBSERVABILITY: bool = os.getenv("ENABLE_KAFKA_OBSERVABILITY", "true").lower() == "true"
    ENABLE_LANGFUSE_TRACING: bool = os.getenv("ENABLE_LANGFUSE_TRACING", "true").lower() == "true"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # .env has extra/legacy keys (e.g. LANGFUSE_BASE_URL) not declared as fields


settings = Settings()
