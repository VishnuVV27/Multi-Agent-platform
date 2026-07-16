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

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "multi_agent_ai")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

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
    LITELLM_LOG: bool = os.getenv("LITELLM_LOG", "TRUE").lower() == "true"
    LITELLM_CACHE: bool = os.getenv("LITELLM_CACHE", "false").lower() == "true"

    # Observability
    LANGFUSE_API_KEY: Optional[str] = os.getenv("LANGFUSE_API_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Feature Flags
    ENABLE_APPROVAL_WORKFLOW: bool = os.getenv("ENABLE_APPROVAL_WORKFLOW", "true").lower() == "true"
    ENABLE_KAFKA_OBSERVABILITY: bool = os.getenv("ENABLE_KAFKA_OBSERVABILITY", "true").lower() == "true"
    ENABLE_LANGFUSE_TRACING: bool = os.getenv("ENABLE_LANGFUSE_TRACING", "true").lower() == "true"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
