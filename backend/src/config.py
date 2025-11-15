from dotenv import load_dotenv
import os
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv()


class Config:
    """Configuration for SupoClip backend (native macOS version).

    Uses:
    - SQLite for database (not PostgreSQL)
    - parakeet-mlx for transcription (not AssemblyAI)
    - Local asyncio queue for jobs (not Redis/arq)
    """

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        # parakeet-mlx transcription model
        # Default: mlx-community/parakeet-tdt-0.6b-v2
        self.parakeet_model = os.getenv(
            "PARAKEET_MODEL", "mlx-community/parakeet-tdt-0.6b-v2"
        )

        # Local LLM configuration (default - no API key required)
        self.local_llm_enabled = (
            os.getenv("LOCAL_LLM_ENABLED", "true").lower() == "true"
        )
        self.local_llm_base_url = os.getenv(
            "LOCAL_LLM_BASE_URL", "http://localhost:6969/v1"
        )
        self.local_llm_model = os.getenv("LOCAL_LLM_MODEL", "local-model")
        self.local_llm_api_key = os.getenv("LOCAL_LLM_API_KEY", "not-needed")

        # Cloud LLM configuration (optional fallback)
        self.llm = os.getenv("LLM_MODEL", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")

        # Video processing settings
        self.max_video_duration = int(os.getenv("MAX_VIDEO_DURATION", "3600"))
        self.output_dir = os.getenv("OUTPUT_DIR", "outputs")

        # Clip generation settings
        self.max_clips = int(os.getenv("MAX_CLIPS", "10"))
        self.clip_duration = int(os.getenv("CLIP_DURATION", "30"))  # seconds

        # Temporary directory for video processing
        self.temp_dir = os.getenv("TEMP_DIR", "temp")

        # Database URL (SQLite)
        self.database_url = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./supoclip.db"
        )

        # Local job queue settings
        self.max_workers = int(os.getenv("MAX_WORKERS", "2"))
        self.worker_timeout = int(os.getenv("WORKER_TIMEOUT", "3600"))

        # Authentication bypass for local development (no sign-in required)
        # Set to true to disable authentication and use default user_id for all requests
        self.disable_auth = os.getenv("DISABLE_AUTH", "false").lower() == "true"
        self.default_user_id = os.getenv("DEFAULT_USER_ID", "local-user")

        # Logging configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_dir = os.getenv("LOG_DIR", "logs")
        self.log_retention_days = int(os.getenv("LOG_RETENTION_DAYS", "30"))

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
                f"Invalid log level: {level}. "
                f"Must be one of: {', '.join(valid_levels)}"
            )
        return level
