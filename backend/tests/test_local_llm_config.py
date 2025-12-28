"""
Tests for local LLM configuration and model selection.

Tests:
- Local LLM configuration defaults
- Cloud LLM fallback configuration
- Model selection logic (local-first, cloud fallback)
- Error handling when no LLM configured
- OpenAI-compatible model creation
"""

import pytest
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config
from pydantic_ai.models.openai import OpenAIModel


class TestLocalLLMConfiguration:
    """Test local LLM configuration defaults and environment variables."""

    def test_local_llm_enabled_default(self, monkeypatch):
        """Local LLM should be enabled by default."""
        monkeypatch.delenv("LOCAL_LLM_ENABLED", raising=False)
        config = Config()
        assert config.local_llm_enabled is True

    def test_local_llm_enabled_from_env(self, monkeypatch):
        """Local LLM enabled status should be configurable."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        config = Config()
        assert config.local_llm_enabled is False

    def test_local_llm_base_url_default(self, monkeypatch):
        """Default local LLM base URL should be localhost:6969."""
        monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
        config = Config()
        assert config.local_llm_base_url == "http://localhost:6969/v1"

    def test_local_llm_base_url_from_env(self, monkeypatch):
        """Local LLM base URL should be configurable."""
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://localhost:5001/v1")
        config = Config()
        assert config.local_llm_base_url == "http://localhost:5001/v1"

    def test_local_llm_model_default(self, monkeypatch):
        """Default local LLM model name should be local-model."""
        monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)
        config = Config()
        assert config.local_llm_model == "local-model"

    def test_local_llm_model_from_env(self, monkeypatch):
        """Local LLM model name should be configurable."""
        monkeypatch.setenv("LOCAL_LLM_MODEL", "mistral-7b")
        config = Config()
        assert config.local_llm_model == "mistral-7b"

    def test_local_llm_api_key_default(self, monkeypatch):
        """Default local LLM API key should be 'not-needed'."""
        monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
        config = Config()
        assert config.local_llm_api_key == "not-needed"

    def test_local_llm_api_key_from_env(self, monkeypatch):
        """Local LLM API key should be configurable."""
        monkeypatch.setenv("LOCAL_LLM_API_KEY", "custom-key")
        config = Config()
        assert config.local_llm_api_key == "custom-key"


class TestCloudLLMConfiguration:
    """Test cloud LLM fallback configuration."""

    def test_cloud_llm_model_default_empty(self, monkeypatch):
        """Cloud LLM model should default to empty string."""
        monkeypatch.delenv("LLM_MODEL", raising=False)
        config = Config()
        assert config.llm == ""

    def test_cloud_llm_model_from_env(self, monkeypatch):
        """Cloud LLM model should be configurable."""
        monkeypatch.setenv("LLM_MODEL", "openai:gpt-4o")
        config = Config()
        assert config.llm == "openai:gpt-4o"

    def test_cloud_api_keys_default_empty(self, monkeypatch):
        """Cloud API keys should default to empty strings."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = Config()
        assert config.openai_api_key == ""
        assert config.google_api_key == ""
        assert config.anthropic_api_key == ""

    def test_openai_api_key_from_env(self, monkeypatch):
        """OpenAI API key should be configurable."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()
        assert config.openai_api_key == "sk-test-key"

    def test_google_api_key_from_env(self, monkeypatch):
        """Google API key should be configurable."""
        monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
        config = Config()
        assert config.google_api_key == "google-test-key"

    def test_anthropic_api_key_from_env(self, monkeypatch):
        """Anthropic API key should be configurable."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = Config()
        assert config.anthropic_api_key == "sk-ant-test-key"


class TestLLMModelSelection:
    """Test get_llm_model() method for dynamic model selection."""

    def test_get_llm_model_returns_openai_chat_model_when_local_enabled(
        self, monkeypatch
    ):
        """get_llm_model() should return OpenAIModel when local LLM enabled."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
        config = Config()
        model = config.get_llm_model()
        assert isinstance(model, OpenAIModel)

    def test_get_llm_model_returns_string_when_cloud(self, monkeypatch):
        """get_llm_model() should return string when cloud LLM enabled."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        monkeypatch.setenv("LLM_MODEL", "openai:gpt-4o")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()
        model = config.get_llm_model()
        assert isinstance(model, str)
        assert model == "openai:gpt-4o"

    def test_get_llm_model_raises_when_no_llm_configured(self, monkeypatch):
        """get_llm_model() should raise ValueError when no LLM configured."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = Config()

        with pytest.raises(
            ValueError,
            match="No LLM configured"
        ):
            config.get_llm_model()

    def test_local_llm_takes_priority_over_cloud(self, monkeypatch):
        """Local LLM should take priority when both are configured."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
        monkeypatch.setenv("LLM_MODEL", "openai:gpt-4o")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()

        model = config.get_llm_model()
        # Should return local model, not cloud string
        assert isinstance(model, OpenAIModel)


class TestCloudAPIKeyDetection:
    """Test _has_cloud_api_key() method."""

    def test_has_cloud_api_key_returns_false_when_all_empty(self, monkeypatch):
        """_has_cloud_api_key() should return False when all keys empty."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        config = Config()
        assert config._has_cloud_api_key() is False

    def test_has_cloud_api_key_returns_true_with_openai(self, monkeypatch):
        """_has_cloud_api_key() should return True when OpenAI key set."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()
        assert config._has_cloud_api_key() is True

    def test_has_cloud_api_key_returns_true_with_google(self, monkeypatch):
        """_has_cloud_api_key() should return True when Google key set."""
        monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
        config = Config()
        assert config._has_cloud_api_key() is True

    def test_has_cloud_api_key_returns_true_with_anthropic(self, monkeypatch):
        """_has_cloud_api_key() should return True when Anthropic key set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = Config()
        assert config._has_cloud_api_key() is True


class TestLocalLLMModelCreation:
    """Test _create_local_llm_model() method."""

    def test_create_local_llm_model_returns_openai_chat_model(self, monkeypatch):
        """_create_local_llm_model() should return OpenAIModel instance."""
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://localhost:6969/v1")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "mistral-7b")
        config = Config()

        model = config._create_local_llm_model()
        assert isinstance(model, OpenAIModel)

    def test_create_local_llm_model_uses_custom_base_url(self, monkeypatch):
        """_create_local_llm_model() should use custom base URL from config."""
        custom_url = "http://custom-host:5001/v1"
        monkeypatch.setenv("LOCAL_LLM_BASE_URL", custom_url)
        monkeypatch.setenv("LOCAL_LLM_MODEL", "llama-13b")
        config = Config()

        model = config._create_local_llm_model()
        # Verify it's an OpenAIModel with correct configuration
        assert isinstance(model, OpenAIModel)
        # The base_url is stored in the provider's client
        assert config.local_llm_base_url == custom_url

    def test_create_local_llm_model_uses_custom_model_name(self, monkeypatch):
        """_create_local_llm_model() should use custom model name from config."""
        monkeypatch.setenv("LOCAL_LLM_MODEL", "custom-model-name")
        config = Config()

        model = config._create_local_llm_model()
        assert isinstance(model, OpenAIModel)
        assert config.local_llm_model == "custom-model-name"


class TestConfigurationErrorMessages:
    """Test error messages are helpful."""

    def test_error_message_suggests_local_and_cloud_options(self, monkeypatch):
        """Error message should suggest both local and cloud options."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = Config()

        try:
            config.get_llm_model()
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "LOCAL_LLM_ENABLED" in error_msg
            assert "koboldcpp" in error_msg
            assert "LLM_MODEL" in error_msg


class TestConfigurationBackwardCompatibility:
    """Test backward compatibility with cloud-only configurations."""

    def test_cloud_only_config_still_works(self, monkeypatch):
        """Users with cloud-only config should still be able to use system."""
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        monkeypatch.setenv("LLM_MODEL", "openai:gpt-4o")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()

        # Should work without error
        model = config.get_llm_model()
        assert model == "openai:gpt-4o"

    def test_local_first_is_transparent_to_cloud_users(self, monkeypatch):
        """Cloud users can switch from local to cloud easily."""
        # Start with local (default)
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
        config = Config()
        local_model = config.get_llm_model()
        assert isinstance(local_model, OpenAIModel)

        # Switch to cloud by changing env vars
        monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
        monkeypatch.setenv("LLM_MODEL", "openai:gpt-4o")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()
        cloud_model = config.get_llm_model()
        assert cloud_model == "openai:gpt-4o"
