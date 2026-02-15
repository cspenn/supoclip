# start backend/src/config.py

"""Configuration for SupoClip backend, validated via Pydantic BaseSettings.

Uses:
- SQLite for database (not PostgreSQL)
- parakeet-mlx for local transcription
- Local asyncio queue for jobs (not Redis/arq)
"""

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import Field
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Config(BaseSettings):
    """Configuration for SupoClip backend (native macOS version).

    Uses:
    - SQLite for database (not PostgreSQL)
    - parakeet-mlx for local transcription
    - Local asyncio queue for jobs (not Redis/arq)
    """

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    # Default ports
    DEFAULT_BACKEND_PORT: int = 8008

    # parakeet-mlx transcription model
    parakeet_model: str = Field(
        default="mlx-community/parakeet-tdt-0.6b-v2",
        validation_alias="PARAKEET_MODEL",
    )

    # Word reconstruction using Groq LLM (fixes broken sub-word tokens)
    reconstruct_words_with_llm: bool = Field(
        default=True,
        validation_alias="RECONSTRUCT_WORDS_WITH_LLM",
    )

    # Local LLM configuration (default - no API key required)
    local_llm_enabled: bool = Field(
        default=True,
        validation_alias="LOCAL_LLM_ENABLED",
    )
    local_llm_base_url: str = Field(
        default="http://localhost:6969/v1",
        validation_alias="LOCAL_LLM_BASE_URL",
    )
    local_llm_model: str = Field(
        default="local-model",
        validation_alias="LOCAL_LLM_MODEL",
    )
    local_llm_api_key: str = Field(
        default="not-needed",
        validation_alias="LOCAL_LLM_API_KEY",
    )

    # Cloud LLM configuration (optional fallback)
    llm: str = Field(default="", validation_alias="LLM_MODEL")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", validation_alias="GOOGLE_API_KEY")

    # Video processing settings
    max_video_duration: int = Field(default=3600, validation_alias="MAX_VIDEO_DURATION")
    output_dir: str = Field(default="outputs", validation_alias="OUTPUT_DIR")

    # Clip generation settings
    max_clips: int = Field(default=10, validation_alias="MAX_CLIPS")
    clip_duration: int = Field(default=30, validation_alias="CLIP_DURATION")

    # Temporary directory for video processing
    temp_dir: str = Field(default="temp", validation_alias="TEMP_DIR")

    # Database URL (SQLite)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./supoclip.db",
        validation_alias="DATABASE_URL",
    )

    # Local job queue settings
    max_workers: int = Field(default=2, validation_alias="MAX_WORKERS")
    worker_timeout: int = Field(default=3600, validation_alias="WORKER_TIMEOUT")

    # Authentication bypass for local development
    disable_auth: bool = Field(default=False, validation_alias="DISABLE_AUTH")
    default_user_id: str = Field(default="local-user", validation_alias="DEFAULT_USER_ID")

    # Logging configuration
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_dir: str = Field(default="logs", validation_alias="LOG_DIR")
    log_retention_days: int = Field(default=30, validation_alias="LOG_RETENTION_DAYS")

    # Backend URL (for generating full URLs to clips)
    backend_url: str = Field(
        default="http://localhost:8008",
        validation_alias="BACKEND_URL",
    )

    # Gradual rollout percentage for async service
    async_rollout_percentage: int = Field(
        default=0,
        validation_alias="ASYNC_ROLLOUT_PERCENTAGE",
    )

    def get_llm_model(self) -> OpenAIModel | str:
        """Get configured LLM model (local-first, cloud fallback).

        Returns:
            OpenAIModel for local LLM or str for cloud LLM model identifier.

        Raises:
            ValueError: If no LLM is configured.
        """
        if self.local_llm_enabled:
            return self._create_local_llm_model()
        elif self.llm and self._has_cloud_api_key():
            return self.llm
        else:
            raise ValueError(
                "No LLM configured. Either:\n"
                "1. Enable local LLM: LOCAL_LLM_ENABLED=true and start koboldcpp\n"
                "2. Configure cloud LLM: Set LLM_MODEL and appropriate API key"
            )

    def _create_local_llm_model(self) -> OpenAIModel:
        """Create OpenAI-compatible model for local LLM.

        Returns:
            OpenAIModel configured for local endpoint.
        """
        client = AsyncOpenAI(
            base_url=self.local_llm_base_url,
            api_key=self.local_llm_api_key,
            max_retries=3,
            timeout=120.0,
        )

        return OpenAIModel(
            self.local_llm_model, provider=OpenAIProvider(openai_client=client)
        )

    def _has_cloud_api_key(self) -> bool:
        """Check if any cloud API key is configured.

        Returns:
            True if at least one cloud API key is set.
        """
        return bool(
            self.groq_api_key
            or self.openai_api_key
            or self.anthropic_api_key
            or self.google_api_key
        )

    def get_log_level(self) -> str:
        """Get validated log level.

        Returns:
            Validated log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

        Raises:
            ValueError: If log level is invalid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level = self.log_level.upper()
        if level not in valid_levels:
            raise ValueError(
                f"Invalid log level: {level}. Must be one of: {', '.join(valid_levels)}"
            )
        return level

# end backend/src/config.py
