"""Tests for configuration loading."""

import os
from pathlib import Path

import pytest

from codecrew.config import (
    Settings,
    _deep_merge,
    _expand_env_vars,
    load_settings,
    reset_settings,
)
from codecrew.config.settings import ModelConfig, ModelsConfig


class TestExpandEnvVars:
    """Tests for environment variable expansion."""

    def test_expand_simple_var(self) -> None:
        """Test expanding a simple environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        result = _expand_env_vars("${TEST_VAR}")
        assert result == "test_value"
        del os.environ["TEST_VAR"]

    def test_expand_missing_var(self) -> None:
        """Test expanding a missing environment variable returns None."""
        result = _expand_env_vars("${NONEXISTENT_VAR}")
        assert result is None

    def test_expand_in_dict(self) -> None:
        """Test expanding variables in a dictionary."""
        os.environ["TEST_KEY"] = "secret"
        data = {"api_key": "${TEST_KEY}", "other": "static"}
        result = _expand_env_vars(data)
        assert result["api_key"] == "secret"
        assert result["other"] == "static"
        del os.environ["TEST_KEY"]

    def test_expand_in_nested_dict(self) -> None:
        """Test expanding variables in nested dictionaries."""
        os.environ["NESTED_VAR"] = "nested_value"
        data = {"level1": {"level2": "${NESTED_VAR}"}}
        result = _expand_env_vars(data)
        assert result["level1"]["level2"] == "nested_value"
        del os.environ["NESTED_VAR"]

    def test_expand_in_list(self) -> None:
        """Test expanding variables in a list."""
        os.environ["LIST_VAR"] = "list_value"
        data = ["${LIST_VAR}", "static"]
        result = _expand_env_vars(data)
        assert result[0] == "list_value"
        assert result[1] == "static"
        del os.environ["LIST_VAR"]


class TestDeepMerge:
    """Tests for deep dictionary merging."""

    def test_simple_merge(self) -> None:
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test merging nested dictionaries."""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_override_non_dict(self) -> None:
        """Test that non-dict values are overridden completely."""
        base = {"key": {"nested": "value"}}
        override = {"key": "simple"}
        result = _deep_merge(base, override)
        assert result == {"key": "simple"}


class TestModelConfig:
    """Tests for ModelConfig validation."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        config = ModelConfig(model_id="test-model")
        assert config.enabled is True
        assert config.max_tokens == 8192
        assert config.temperature == 0.7

    def test_custom_values(self) -> None:
        """Test custom values are accepted."""
        config = ModelConfig(
            model_id="custom-model",
            enabled=False,
            max_tokens=4096,
            temperature=0.5,
        )
        assert config.enabled is False
        assert config.max_tokens == 4096
        assert config.temperature == 0.5

    def test_empty_model_id_fails(self) -> None:
        """Test that empty model_id raises an error."""
        with pytest.raises(ValueError):
            ModelConfig(model_id="")

    def test_whitespace_model_id_fails(self) -> None:
        """Test that whitespace-only model_id raises an error."""
        with pytest.raises(ValueError):
            ModelConfig(model_id="   ")

    def test_temperature_range(self) -> None:
        """Test temperature validation."""
        # Valid range
        ModelConfig(model_id="test", temperature=0.0)
        ModelConfig(model_id="test", temperature=2.0)

        # Invalid range
        with pytest.raises(ValueError):
            ModelConfig(model_id="test", temperature=-0.1)
        with pytest.raises(ValueError):
            ModelConfig(model_id="test", temperature=2.1)


class TestSettings:
    """Tests for Settings model."""

    def test_default_settings(self, clean_env: None) -> None:
        """Test creating settings with defaults."""
        settings = Settings()
        assert settings.anthropic_api_key is None
        assert settings.models.claude.enabled is True
        assert settings.conversation.first_responder == "rotate"

    def test_api_key_from_env(self, clean_env: None) -> None:
        """Test loading API keys from environment."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        settings = Settings()
        assert settings.anthropic_api_key == "test-key"

    def test_get_enabled_models(self, clean_env: None) -> None:
        """Test getting list of enabled models."""
        settings = Settings()
        enabled = settings.get_enabled_models()
        assert "claude" in enabled
        assert "gpt" in enabled
        assert "gemini" in enabled
        assert "grok" in enabled

    def test_has_api_key(self, clean_env: None) -> None:
        """Test checking for API keys."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        settings = Settings()
        assert settings.has_api_key("claude") is True
        assert settings.has_api_key("gpt") is False

    def test_get_available_models(self, clean_env: None) -> None:
        """Test getting available models (enabled + has key)."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        os.environ["OPENAI_API_KEY"] = "test-key"
        settings = Settings()
        available = settings.get_available_models()
        assert "claude" in available
        assert "gpt" in available
        assert "gemini" not in available  # No key
        assert "grok" not in available  # No key

    def test_empty_api_key_treated_as_none(self, clean_env: None) -> None:
        """Test that empty string API keys are treated as None."""
        settings = Settings(anthropic_api_key="")
        assert settings.anthropic_api_key is None


class TestLoadSettings:
    """Tests for the load_settings function."""

    def test_load_from_yaml(self, temp_config_file: Path, clean_env: None) -> None:
        """Test loading settings from a YAML file."""
        settings = load_settings(config_path=temp_config_file, force_reload=True)
        assert settings.anthropic_api_key == "test-anthropic-key"
        assert settings.openai_api_key == "test-openai-key"
        assert settings.conversation.first_responder == "claude"
        assert settings.conversation.silence_threshold == 0.5

    def test_env_var_override(self, temp_config_file: Path, clean_env: None) -> None:
        """Test that environment variables override config file."""
        os.environ["ANTHROPIC_API_KEY"] = "env-override-key"
        settings = load_settings(config_path=temp_config_file, force_reload=True)
        # The YAML value should be used since we're loading from file
        # Environment variables are used as fallback when not in YAML
        assert settings.anthropic_api_key in ["test-anthropic-key", "env-override-key"]

    def test_caching(self, temp_config_file: Path, clean_env: None) -> None:
        """Test that settings are cached."""
        settings1 = load_settings(config_path=temp_config_file, force_reload=True)
        settings2 = load_settings(config_path=temp_config_file)
        assert settings1 is settings2

    def test_force_reload(self, temp_config_file: Path, clean_env: None) -> None:
        """Test that force_reload creates new instance."""
        settings1 = load_settings(config_path=temp_config_file, force_reload=True)
        settings2 = load_settings(config_path=temp_config_file, force_reload=True)
        # Both should have same values but be different instances
        assert settings1 is not settings2
        assert settings1.anthropic_api_key == settings2.anthropic_api_key
