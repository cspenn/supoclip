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


# end tests/unit/test_config.py
