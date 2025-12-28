"""
Configuration tests for SupoClip backend.

Tests:
- Config loading from environment variables
- Default values when environment variables are missing
- Type conversion and validation
- Required vs optional configuration
- Database and model configuration
"""
import os
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config


class TestConfigLoading:
    """Test configuration loading and defaults."""

    def test_config_initialization(self, test_config):
        """Test that config initializes without errors."""
        assert test_config is not None
        assert isinstance(test_config, Config)

    def test_parakeet_model_default(self, monkeypatch):
        """Test parakeet-mlx model defaults to parakeet-tdt-0.6b-v2."""
        monkeypatch.delenv("PARAKEET_MODEL", raising=False)
        config = Config()
        assert config.parakeet_model == "mlx-community/parakeet-tdt-0.6b-v2"

    def test_parakeet_model_from_env(self, monkeypatch):
        """Test parakeet-mlx model can be set from environment."""
        monkeypatch.setenv("PARAKEET_MODEL", "mlx-community/parakeet-tdt-1.1b")
        config = Config()
        assert config.parakeet_model == "mlx-community/parakeet-tdt-1.1b"

    def test_llm_model_default(self, monkeypatch):
        """Test LLM model defaults to empty string (local-first)."""
        monkeypatch.delenv("LLM_MODEL", raising=False)
        config = Config()
        assert config.llm == ""

    def test_llm_model_from_env(self, monkeypatch):
        """Test LLM model can be set from environment."""
        monkeypatch.setenv("LLM_MODEL", "anthropic:claude-3-5-sonnet")
        config = Config()
        assert config.llm == "anthropic:claude-3-5-sonnet"

    def test_api_keys_optional(self, monkeypatch):
        """Test that API keys are optional."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        config = Config()

        assert config.openai_api_key == ""
        assert config.anthropic_api_key == ""
        assert config.google_api_key == ""


class TestVideoProcessingConfig:
    """Test video processing configuration."""

    def test_max_video_duration_default(self, monkeypatch):
        """Test max video duration defaults to 1 hour."""
        monkeypatch.delenv("MAX_VIDEO_DURATION", raising=False)
        config = Config()
        assert config.max_video_duration == 3600

    def test_max_video_duration_from_env(self, monkeypatch):
        """Test max video duration from environment."""
        monkeypatch.setenv("MAX_VIDEO_DURATION", "7200")
        config = Config()
        assert config.max_video_duration == 7200

    def test_output_dir_default(self, monkeypatch):
        """Test output directory defaults to 'outputs'."""
        monkeypatch.delenv("OUTPUT_DIR", raising=False)
        config = Config()
        assert config.output_dir == "outputs"

    def test_output_dir_from_env(self, monkeypatch, temp_dir):
        """Test output directory from environment."""
        output_path = str(temp_dir / "custom_output")
        monkeypatch.setenv("OUTPUT_DIR", output_path)
        config = Config()
        assert config.output_dir == output_path

    def test_max_clips_default(self, monkeypatch):
        """Test max clips defaults to 10."""
        monkeypatch.delenv("MAX_CLIPS", raising=False)
        config = Config()
        assert config.max_clips == 10

    def test_max_clips_from_env(self, monkeypatch):
        """Test max clips from environment."""
        monkeypatch.setenv("MAX_CLIPS", "5")
        config = Config()
        assert config.max_clips == 5

    def test_clip_duration_default(self, monkeypatch):
        """Test clip duration defaults to 30 seconds."""
        monkeypatch.delenv("CLIP_DURATION", raising=False)
        config = Config()
        assert config.clip_duration == 30

    def test_clip_duration_from_env(self, monkeypatch):
        """Test clip duration from environment."""
        monkeypatch.setenv("CLIP_DURATION", "45")
        config = Config()
        assert config.clip_duration == 45


class TestDatabaseConfig:
    """Test database configuration."""

    def test_database_url_default(self, monkeypatch):
        """Test database URL defaults to SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        config = Config()
        assert config.database_url == "sqlite+aiosqlite:///./supoclip.db"

    def test_database_url_from_env(self, monkeypatch):
        """Test database URL from environment."""
        db_url = "sqlite+aiosqlite:////tmp/test.db"
        monkeypatch.setenv("DATABASE_URL", db_url)
        config = Config()
        assert config.database_url == db_url

    def test_temp_dir_default(self, monkeypatch):
        """Test temp directory defaults to 'temp'."""
        monkeypatch.delenv("TEMP_DIR", raising=False)
        config = Config()
        assert config.temp_dir == "temp"

    def test_temp_dir_from_env(self, monkeypatch, temp_dir):
        """Test temp directory from environment."""
        monkeypatch.setenv("TEMP_DIR", str(temp_dir))
        config = Config()
        assert config.temp_dir == str(temp_dir)


class TestJobQueueConfig:
    """Test job queue configuration."""

    def test_max_workers_default(self, monkeypatch):
        """Test max workers defaults to 2."""
        monkeypatch.delenv("MAX_WORKERS", raising=False)
        config = Config()
        assert config.max_workers == 2

    def test_max_workers_from_env(self, monkeypatch):
        """Test max workers from environment."""
        monkeypatch.setenv("MAX_WORKERS", "4")
        config = Config()
        assert config.max_workers == 4

    def test_worker_timeout_default(self, monkeypatch):
        """Test worker timeout defaults to 1 hour."""
        monkeypatch.delenv("WORKER_TIMEOUT", raising=False)
        config = Config()
        assert config.worker_timeout == 3600

    def test_worker_timeout_from_env(self, monkeypatch):
        """Test worker timeout from environment."""
        monkeypatch.setenv("WORKER_TIMEOUT", "7200")
        config = Config()
        assert config.worker_timeout == 7200


class TestConfigTypeConversion:
    """Test that configuration values are converted to correct types."""

    def test_integer_type_conversion(self, monkeypatch):
        """Test that string environment variables are converted to integers."""
        monkeypatch.setenv("MAX_WORKERS", "8")
        monkeypatch.setenv("WORKER_TIMEOUT", "5000")

        config = Config()

        assert isinstance(config.max_workers, int)
        assert isinstance(config.worker_timeout, int)
        assert config.max_workers == 8
        assert config.worker_timeout == 5000

    def test_string_type_preserved(self, monkeypatch):
        """Test that string values remain as strings."""
        monkeypatch.setenv("LLM_MODEL", "test:model")
        monkeypatch.setenv("TEMP_DIR", "/custom/path")

        config = Config()

        assert isinstance(config.llm, str)
        assert isinstance(config.temp_dir, str)


class TestConfigValidation:
    """Test configuration validation and edge cases."""

    def test_empty_string_handling(self, monkeypatch):
        """Test that empty environment variables are handled."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        config = Config()

        # Empty string should be treated as missing
        assert config.openai_api_key == ""

    def test_whitespace_handling(self, monkeypatch):
        """Test that whitespace in values is preserved."""
        test_value = " test_value_with_spaces "
        monkeypatch.setenv("TEMP_DIR", test_value)

        config = Config()
        assert config.temp_dir == test_value

    def test_special_characters_in_paths(self, monkeypatch, temp_dir):
        """Test that special characters in paths work."""
        special_path = str(temp_dir / "path-with-dashes_and_underscores")
        monkeypatch.setenv("TEMP_DIR", special_path)

        config = Config()
        assert config.temp_dir == special_path

    def test_multiple_config_instances_independent(self, monkeypatch):
        """Test that multiple Config instances don't affect each other."""
        monkeypatch.setenv("MAX_WORKERS", "2")
        config1 = Config()
        assert config1.max_workers == 2

        monkeypatch.setenv("MAX_WORKERS", "4")
        config2 = Config()
        assert config2.max_workers == 4
        assert config1.max_workers == 2  # Should not be affected


class TestOfflineCapability:
    """Test that configuration supports offline operation."""

    def test_no_external_api_required_by_default(self):
        """Test that config can be initialized without external APIs."""
        # Ensure no environment variables are set
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

        # Should initialize without errors
        config = Config()
        assert config is not None

    def test_parakeet_available_offline(self, monkeypatch):
        """Test parakeet-mlx is configured for offline use."""
        monkeypatch.setenv("PARAKEET_MODEL", "mlx-community/parakeet-tdt-0.6b-v2")
        config = Config()

        # parakeet-mlx models are downloaded locally, not cloud-based
        assert config.parakeet_model == "mlx-community/parakeet-tdt-0.6b-v2"

    def test_local_job_queue_configuration(self, monkeypatch):
        """Test that local job queue is configured."""
        monkeypatch.setenv("MAX_WORKERS", "2")
        config = Config()

        # Configuration should support local queue
        assert config.max_workers > 0
        assert config.worker_timeout > 0
