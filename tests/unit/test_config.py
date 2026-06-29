# start tests/unit/test_config.py
"""Unit tests for src/config.py."""

from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from src.config import Config, get_config
from src.exceptions import ConfigurationError


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_loads_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config() initializes successfully with all defaults."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        for var in (
            "HOST",
            "LOG_DIR",
            "MAX_WORKERS",
            "MAX_VIDEO_DURATION",
            "MAX_CLIPS",
            "FFMPEG_PRESET",
            "FFMPEG_CRF",
            "PARAKEET_MODEL",
        ):
            monkeypatch.delenv(var, raising=False)
        # Temporarily suppress .env file loading to test Pydantic defaults
        from pydantic_settings import SettingsConfigDict

        original = Config.model_config
        Config.model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)
        try:
            config = Config()
            assert config.host == "0.0.0.0"  # noqa: S104
            assert config.log_level == "INFO"
            assert config.log_dir == Path("./logs")
            assert config.database_url == "sqlite+aiosqlite:///./supoclip.db"
            assert config.local_llm_enabled is True
            assert config.local_llm_base_url == "http://localhost:6969/v1"
            assert config.local_llm_model == "local-model"
            assert config.llm_model == ""
            assert config.default_min_clip_length == 15
            assert config.default_max_clip_length == 45
            # M-7 fields
            assert config.max_workers == 2
            assert config.ffmpeg_preset == "fast"
            assert config.ffmpeg_crf == 23
            assert config.max_video_duration == 0
            assert config.max_clips == 7
            assert config.parakeet_model == "mlx-community/parakeet-tdt-0.6b-v2"
        finally:
            Config.model_config = original

    def test_class_vars(self) -> None:
        """ClassVar constants are set correctly."""
        assert Path("fonts") == Config.FONTS_DIR
        assert Path("transitions") == Config.TRANSITIONS_DIR

    def test_env_overrides_new_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """M-7 fields are overridable via their env var aliases."""
        monkeypatch.setenv("MAX_WORKERS", "8")
        monkeypatch.setenv("FFMPEG_PRESET", "slow")
        monkeypatch.setenv("FFMPEG_CRF", "18")
        monkeypatch.setenv("MAX_CLIPS", "3")
        monkeypatch.setenv("HOST", "127.0.0.1")
        original = Config.model_config
        Config.model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)
        try:
            config = Config()
            assert config.max_workers == 8
            assert config.ffmpeg_preset == "slow"
            assert config.ffmpeg_crf == 18
            assert config.max_clips == 3
            assert config.host == "127.0.0.1"
        finally:
            Config.model_config = original

    def test_temp_dir_is_path(self) -> None:
        """temp_dir field is a Path object."""
        config = Config()
        assert isinstance(config.temp_dir, Path)


class TestGetConfig:
    """Tests for the get_config() cached singleton."""

    def test_returns_config_instance(self) -> None:
        """get_config() returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_returns_same_instance(self) -> None:
        """get_config() returns the same cached instance on repeated calls."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


class TestGetLlmModel:
    """Tests for Config.get_llm_model()."""

    def test_local_llm_enabled_returns_openai_prefix(self) -> None:
        """When local_llm_enabled=True, returns openai:<model_name>."""
        config = Config(LOCAL_LLM_ENABLED=True, LOCAL_LLM_MODEL="my-local-model")
        result = config.get_llm_model()
        assert result == "openai:my-local-model"

    def test_local_llm_enabled_uses_configured_model(self) -> None:
        """When local_llm_enabled=True, uses local_llm_model value."""
        config = Config(LOCAL_LLM_ENABLED=True, LOCAL_LLM_MODEL="custom-model")
        assert config.get_llm_model() == "openai:custom-model"

    def test_local_llm_disabled_returns_llm_model(self) -> None:
        """When local_llm_enabled=False and llm_model set, returns llm_model."""
        config = Config(
            LOCAL_LLM_ENABLED=False,
            LLM_MODEL="groq:llama-3",
        )
        assert config.get_llm_model() == "groq:llama-3"

    def test_local_llm_disabled_no_model_raises(self) -> None:
        """When local_llm_enabled=False and no llm_model, raises ConfigurationError."""
        config = Config(LOCAL_LLM_ENABLED=False, LLM_MODEL="")
        with pytest.raises(ConfigurationError, match="No LLM configured"):
            config.get_llm_model()


class TestEnsureTempDirs:
    """Tests for Config.ensure_temp_dirs()."""

    def test_creates_temp_directories(self, tmp_path: Path) -> None:
        """ensure_temp_dirs() creates temp/, temp/uploads/, temp/clips/."""
        temp_root = tmp_path / "mytemp"
        config = Config(TEMP_DIR=str(temp_root))
        config.ensure_temp_dirs()

        assert temp_root.is_dir()
        assert (temp_root / "uploads").is_dir()
        assert (temp_root / "clips").is_dir()

    def test_idempotent_when_dirs_exist(self, tmp_path: Path) -> None:
        """ensure_temp_dirs() does not raise when dirs already exist."""
        temp_root = tmp_path / "mytemp"
        temp_root.mkdir(parents=True)
        config = Config(TEMP_DIR=str(temp_root))
        config.ensure_temp_dirs()  # should not raise
        config.ensure_temp_dirs()  # calling again is safe


class TestVlmConfig:
    """Tests for the VLM / content-mode configuration (vision-aware clipping)."""

    def test_defaults(self) -> None:
        """VLM is off by default; content_mode defaults to single."""
        config = Config()
        assert config.content_mode == "single"
        assert config.vlm_enabled is False
        assert config.vlm_model == ""
        assert config.vlm_max_tokens == 512
        assert config.vlm_frames_per_clip == 5
        assert config.vlm_image_max_dim == 768
        assert config.vlm_timeout_s == pytest.approx(180.0)

    def test_env_overrides(self) -> None:
        """Every VLM tunable is overridable via its env alias."""
        config = Config(
            CONTENT_MODE="duo",
            VLM_ENABLED=True,
            VLM_MODEL="Qwen3.6-35B-A3B-Mixed-4-8",
            VLM_MAX_TOKENS=1024,
            VLM_FRAMES_PER_CLIP=8,
            VLM_IMAGE_MAX_DIM=512,
            VLM_TIMEOUT_S=90.0,
        )
        assert config.content_mode == "duo"
        assert config.vlm_enabled is True
        assert config.vlm_model == "Qwen3.6-35B-A3B-Mixed-4-8"
        assert config.vlm_max_tokens == 1024
        assert config.vlm_frames_per_clip == 8
        assert config.vlm_image_max_dim == 512
        assert config.vlm_timeout_s == pytest.approx(90.0)

    def test_invalid_content_mode_rejected(self) -> None:
        """content_mode only accepts single/duo/multi."""
        with pytest.raises(ValueError):
            Config(CONTENT_MODE="quad")

    def test_vlm_endpoint_falls_back_to_local_llm(self) -> None:
        """When vlm_base_url/api_key are unset, the local LLM endpoint is reused."""
        config = Config(LOCAL_LLM_BASE_URL="http://localhost:1/v1", LOCAL_LLM_API_KEY="k")
        assert config.get_vlm_base_url() == "http://localhost:1/v1"
        assert config.get_vlm_api_key() == "k"

    def test_vlm_endpoint_overrides_local_llm(self) -> None:
        """Explicit vlm_base_url/api_key take precedence over the local LLM ones."""
        config = Config(
            LOCAL_LLM_BASE_URL="http://localhost:1/v1",
            LOCAL_LLM_API_KEY="k",
            VLM_BASE_URL="http://localhost:2/v1",
            VLM_API_KEY="vk",
        )
        assert config.get_vlm_base_url() == "http://localhost:2/v1"
        assert config.get_vlm_api_key() == "vk"


# end tests/unit/test_config.py
