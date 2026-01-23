"""
Application Configuration
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ClaimBot"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False  # Secure default
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/claimbot"
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Provider
    LLM_PROVIDER: Literal["bedrock", "ollama"] = "ollama"

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Escalation Thresholds
    CONFIDENCE_THRESHOLD: float = 0.7
    AUTO_APPROVAL_LIMIT: float = 5000.0

    # LangFuse Observability (optional)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate critical settings for non-development environments."""
        if self.APP_ENV != "development":
            # Reject default SECRET_KEY in production/staging
            if self.SECRET_KEY == "change-me-in-production":
                raise ValueError(
                    "SECRET_KEY must be changed from default value in production/staging environments. "
                    "Set a secure, random SECRET_KEY in your .env file or environment variables."
                )

            # Warn about DEBUG mode in production
            if self.DEBUG:
                import warnings
                warnings.warn(
                    "DEBUG mode is enabled in a non-development environment. "
                    "This is not recommended for production.",
                    UserWarning,
                )

        # Validate AWS credentials when using Bedrock
        if self.LLM_PROVIDER == "bedrock":
            if not self.AWS_ACCESS_KEY_ID or not self.AWS_SECRET_ACCESS_KEY:
                raise ValueError(
                    "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required when LLM_PROVIDER is 'bedrock'. "
                    "Set these in your .env file or environment variables."
                )

        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
