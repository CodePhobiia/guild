"""Configuration management for CodeCrew."""

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from .settings import Settings

# Singleton instance
_settings: Optional[Settings] = None

# Default config directory
CONFIG_DIR = Path.home() / ".codecrew"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULTS_FILE = Path(__file__).parent / "defaults.yaml"


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${ENV_VAR} syntax in strings."""
    if isinstance(value, str):
        # Match ${VAR_NAME} pattern
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)
        for var_name in matches:
            env_value = os.environ.get(var_name, "")
            value = value.replace(f"${{{var_name}}}", env_value)
        return value if value else None
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml_file(path: Path) -> dict:
    """Load a YAML file and return its contents."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
        return content if content else {}


def _transform_config_to_settings(config: dict) -> dict:
    """Transform YAML config structure to Settings model structure."""
    settings_dict = {}

    # Extract API keys from nested structure
    api_keys = config.get("api_keys", {})
    if api_keys:
        if api_keys.get("anthropic"):
            settings_dict["anthropic_api_key"] = api_keys["anthropic"]
        if api_keys.get("openai"):
            settings_dict["openai_api_key"] = api_keys["openai"]
        if api_keys.get("google"):
            settings_dict["google_api_key"] = api_keys["google"]
        if api_keys.get("xai"):
            settings_dict["xai_api_key"] = api_keys["xai"]

    # Copy other sections directly
    for section in ["models", "conversation", "ui", "tools", "storage"]:
        if section in config:
            settings_dict[section] = config[section]

    return settings_dict


def ensure_config_dir() -> None:
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_default_config() -> None:
    """Create a default config file if it doesn't exist."""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        # Copy defaults to user config location
        defaults = DEFAULTS_FILE.read_text(encoding="utf-8")
        CONFIG_FILE.write_text(defaults, encoding="utf-8")


def load_settings(config_path: Optional[Path] = None, force_reload: bool = False) -> Settings:
    """
    Load settings with priority: CLI args > env vars > user config > defaults.

    Args:
        config_path: Optional path to a custom config file
        force_reload: Force reload even if settings are cached

    Returns:
        Settings instance
    """
    global _settings

    if _settings is not None and not force_reload:
        return _settings

    # Ensure config directory exists
    ensure_config_dir()

    # Load defaults
    defaults = _load_yaml_file(DEFAULTS_FILE)

    # Load user config
    user_config_path = config_path or CONFIG_FILE
    user_config = _load_yaml_file(user_config_path)

    # Merge configs (user overrides defaults)
    merged = _deep_merge(defaults, user_config)

    # Expand environment variables in the merged config
    expanded = _expand_env_vars(merged)

    # Transform to settings structure
    settings_dict = _transform_config_to_settings(expanded)

    # Create Settings instance (this also reads from environment variables)
    _settings = Settings(**settings_dict)

    return _settings


def get_settings() -> Settings:
    """Get the current settings instance, loading if necessary."""
    if _settings is None:
        return load_settings()
    return _settings


def reset_settings() -> None:
    """Reset the settings singleton (useful for testing)."""
    global _settings
    _settings = None


__all__ = [
    "Settings",
    "get_settings",
    "load_settings",
    "reset_settings",
    "ensure_config_dir",
    "create_default_config",
    "CONFIG_DIR",
    "CONFIG_FILE",
]
