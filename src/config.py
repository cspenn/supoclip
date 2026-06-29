# start src/config.py
"""Application configuration loaded from environment variables.

All configuration is validated at import time via Pydantic BaseSettings.
Copy .env.example to .env and customize before running.
"""

from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.exceptions import ConfigurationError


class Config(BaseSettings):
    """SupoClip application configuration.

    All values are loaded from environment variables (or .env file).
    Boolean env vars accept 'true'/'false'/'1'/'0' (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    host: str = Field(default="0.0.0.0", validation_alias="HOST")  # noqa: S104
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("./logs"), validation_alias="LOG_DIR")
    temp_dir: Path = Field(default=Path("./temp"), validation_alias="TEMP_DIR")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./supoclip.db",
        validation_alias="DATABASE_URL",
    )

    # Concurrency and video limits
    max_workers: int = Field(default=2, validation_alias="MAX_WORKERS", ge=1)
    max_video_duration: int = Field(default=0, validation_alias="MAX_VIDEO_DURATION", ge=0)
    max_clips: int = Field(default=7, validation_alias="MAX_CLIPS", ge=1)

    # ffmpeg encoding
    ffmpeg_preset: str = Field(default="fast", validation_alias="FFMPEG_PRESET")
    ffmpeg_crf: int = Field(default=23, validation_alias="FFMPEG_CRF", ge=0, le=51)

    # Transcription
    parakeet_model: str = Field(
        default="mlx-community/parakeet-tdt-0.6b-v2",
        validation_alias="PARAKEET_MODEL",
    )

    # Local LLM
    local_llm_enabled: bool = Field(default=True, validation_alias="LOCAL_LLM_ENABLED")
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

    # Cloud LLM (optional)
    llm_model: str = Field(
        default="",
        validation_alias="LLM_MODEL",
    )
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", validation_alias="GOOGLE_API_KEY")

    # Default clip settings
    default_min_clip_length: int = Field(default=15, validation_alias="DEFAULT_MIN_CLIP_LENGTH")
    default_max_clip_length: int = Field(default=45, validation_alias="DEFAULT_MAX_CLIP_LENGTH")

    # Vision / VLM (content-aware clipping — see docs/plans/vlm-enhancement.md).
    # content_mode selects the per-video framing/selection strategy. The VLM is a
    # DISTINCT model from the text-analysis LLM and is OFF by default; every tunable
    # is a named field here (no magic numbers in the vision path).
    content_mode: Literal["single", "duo", "multi"] = Field(default="single", validation_alias="CONTENT_MODE")
    vlm_enabled: bool = Field(default=False, validation_alias="VLM_ENABLED")
    vlm_model: str = Field(default="", validation_alias="VLM_MODEL")
    vlm_base_url: str = Field(default="", validation_alias="VLM_BASE_URL")
    vlm_api_key: str = Field(default="", validation_alias="VLM_API_KEY")
    vlm_max_tokens: int = Field(default=512, validation_alias="VLM_MAX_TOKENS", ge=1)
    vlm_frames_per_clip: int = Field(default=5, validation_alias="VLM_FRAMES_PER_CLIP", ge=1)
    vlm_image_max_dim: int = Field(default=768, validation_alias="VLM_IMAGE_MAX_DIM", ge=64)
    vlm_timeout_s: float = Field(default=180.0, validation_alias="VLM_TIMEOUT_S", gt=0)
    # Engagement re-ranking fuses transcript relevance with the VLM's visual score:
    # fused = transcript_weight * transcript + visual_weight * engagement.
    vlm_rerank_enabled: bool = Field(default=False, validation_alias="VLM_RERANK_ENABLED")
    vlm_transcript_weight: float = Field(default=0.7, validation_alias="VLM_TRANSCRIPT_WEIGHT", ge=0)
    vlm_visual_weight: float = Field(default=0.3, validation_alias="VLM_VISUAL_WEIGHT", ge=0)

    # Internal constants (not from env)
    FONTS_DIR: ClassVar[Path] = Path("fonts")
    TRANSITIONS_DIR: ClassVar[Path] = Path("transitions")

    def get_vlm_base_url(self) -> str:
        """Return the VLM endpoint, falling back to the local LLM endpoint.

        Returns:
            ``vlm_base_url`` when set, otherwise ``local_llm_base_url`` so a
            single local server can serve both the text and vision models.
        """
        return self.vlm_base_url or self.local_llm_base_url

    def get_vlm_api_key(self) -> str:
        """Return the VLM API key, falling back to the local LLM key.

        Returns:
            ``vlm_api_key`` when set, otherwise ``local_llm_api_key``.
        """
        return self.vlm_api_key or self.local_llm_api_key

    def get_llm_model(self) -> str:
        """Return the effective LLM model string.

        Returns the local model spec if local LLM is enabled,
        otherwise returns the cloud LLM_MODEL env var.

        Returns:
            LLM model identifier string for pydantic-ai.

        Raises:
            ConfigurationError: If local LLM is disabled and no ``llm_model``
                is configured, leaving no usable model.
        """
        if self.local_llm_enabled:
            return f"openai:{self.local_llm_model}"
        if not self.llm_model:
            msg = "No LLM configured: set LOCAL_LLM_ENABLED=true or provide LLM_MODEL (e.g. 'openai:gpt-4o')."
            raise ConfigurationError(msg)
        return self.llm_model

    def ensure_temp_dirs(self) -> None:
        """Create temp directory structure if it doesn't exist.

        Creates: temp/, temp/uploads/, temp/clips/
        """
        for subdir in ["", "uploads", "clips"]:
            (self.temp_dir / subdir).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the cached application config singleton.

    Returns:
        The application Config instance, loaded once from environment.
    """
    return Config()


# end src/config.py
