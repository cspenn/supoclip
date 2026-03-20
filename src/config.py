# start src/config.py
"""Application configuration loaded from environment variables.

All configuration is validated at import time via Pydantic BaseSettings.
Copy .env.example to .env and customize before running.
"""
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    app_port: int = Field(default=8008, validation_alias="BACKEND_PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    temp_dir: Path = Field(default=Path("./temp"), validation_alias="TEMP_DIR")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./supoclip.db",
        validation_alias="DATABASE_URL",
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
    default_min_clip_length: int = Field(
        default=15, validation_alias="DEFAULT_MIN_CLIP_LENGTH"
    )
    default_max_clip_length: int = Field(
        default=45, validation_alias="DEFAULT_MAX_CLIP_LENGTH"
    )

    # Internal constants (not from env)
    DEFAULT_BACKEND_PORT: ClassVar[int] = 8008
    FONTS_DIR: ClassVar[Path] = Path("fonts")
    TRANSITIONS_DIR: ClassVar[Path] = Path("transitions")

    def get_llm_model(self) -> str:
        """Return the effective LLM model string.

        Returns the local model spec if local LLM is enabled,
        otherwise returns the cloud LLM_MODEL env var.

        Returns:
            LLM model identifier string for pydantic-ai.
        """
        if self.local_llm_enabled:
            return f"openai:{self.local_llm_model}"
        return self.llm_model or "openai:gpt-4o"

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
