"""Configuration settings models using Pydantic."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseModel):
    """Configuration for an individual AI model."""

    enabled: bool = True
    model_id: str
    max_tokens: int = Field(default=8192, ge=1, le=200000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model_id cannot be empty")
        return v.strip()


class ModelsConfig(BaseModel):
    """Configuration for all AI models."""

    claude: ModelConfig = ModelConfig(model_id="claude-sonnet-4-20250514")
    gpt: ModelConfig = ModelConfig(model_id="gpt-4o")
    gemini: ModelConfig = ModelConfig(model_id="gemini-2.0-flash")
    grok: ModelConfig = ModelConfig(model_id="grok-3")


class ConversationConfig(BaseModel):
    """Configuration for conversation behavior."""

    first_responder: Literal["rotate", "claude", "gpt", "gemini", "grok"] = "rotate"
    silence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    max_context_tokens: int = Field(default=100000, ge=1000)
    auto_save: bool = True
    save_interval_minutes: int = Field(default=5, ge=1)


class UIConfig(BaseModel):
    """Configuration for the user interface."""

    theme: Literal["default", "minimal", "colorblind"] = "default"
    show_silent_models: bool = True
    show_token_usage: bool = False
    show_cost_estimate: bool = True
    code_theme: str = "monokai"


class ToolsConfig(BaseModel):
    """Configuration for tool permissions."""

    file_write: bool = True
    file_delete: Literal["true", "false", "confirm"] = "confirm"
    shell_execute: Literal["true", "false", "confirm"] = "confirm"
    git_operations: bool = True


class StorageConfig(BaseModel):
    """Configuration for data storage."""

    database_path: str = "~/.codecrew/sessions.db"
    max_sessions: int = Field(default=100, ge=1)

    @property
    def resolved_database_path(self) -> Path:
        """Get the resolved database path with ~ expanded."""
        return Path(self.database_path).expanduser()


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="CODECREW_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # API Keys - AliasChoices allows reading from either the field name or PROVIDER_API_KEY
    anthropic_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("anthropic_api_key", "ANTHROPIC_API_KEY"),
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("openai_api_key", "OPENAI_API_KEY"),
    )
    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("google_api_key", "GOOGLE_API_KEY"),
    )
    xai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("xai_api_key", "XAI_API_KEY"),
    )

    # Nested configurations
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @field_validator("anthropic_api_key", "openai_api_key", "google_api_key", "xai_api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate API keys are not empty strings."""
        if v is not None and not v.strip():
            return None
        return v

    def get_enabled_models(self) -> list[str]:
        """Get list of enabled model names."""
        enabled = []
        if self.models.claude.enabled:
            enabled.append("claude")
        if self.models.gpt.enabled:
            enabled.append("gpt")
        if self.models.gemini.enabled:
            enabled.append("gemini")
        if self.models.grok.enabled:
            enabled.append("grok")
        return enabled

    def has_api_key(self, model: str) -> bool:
        """Check if an API key exists for the given model."""
        key_map = {
            "claude": self.anthropic_api_key,
            "gpt": self.openai_api_key,
            "gemini": self.google_api_key,
            "grok": self.xai_api_key,
        }
        return key_map.get(model) is not None

    def get_available_models(self) -> list[str]:
        """Get list of models that are both enabled and have API keys."""
        return [m for m in self.get_enabled_models() if self.has_api_key(m)]
