# start tests/unit/test_config.py
"""Unit tests for src/config.py."""
from pathlib import Path

from src.config import Config, get_config


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_loads_with_defaults(self) -> None:
        """Config() initializes successfully with all defaults."""
        config = Config()
        assert config.app_port == 8008
        assert config.log_level == "INFO"
        assert config.database_url == "sqlite+aiosqlite:///./supoclip.db"
        assert config.local_llm_enabled is True
        assert config.local_llm_base_url == "http://localhost:6969/v1"
        assert config.local_llm_model == "local-model"
        assert config.llm_model == ""
        assert config.default_min_clip_length == 15
        assert config.default_max_clip_length == 45

    def test_class_vars(self) -> None:
        """ClassVar constants are set correctly."""
        assert Config.DEFAULT_BACKEND_PORT == 8008
        assert Path("fonts") == Config.FONTS_DIR
        assert Path("transitions") == Config.TRANSITIONS_DIR

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

    def test_local_llm_disabled_no_model_falls_back(self) -> None:
        """When local_llm_enabled=False and no llm_model, falls back to gpt-4o."""
        config = Config(LOCAL_LLM_ENABLED=False, LLM_MODEL="")
        assert config.get_llm_model() == "openai:gpt-4o"


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
