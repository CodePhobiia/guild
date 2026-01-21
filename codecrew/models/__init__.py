"""Model clients and registry for CodeCrew."""

import logging
from typing import Optional, Type

from codecrew.config import Settings, get_settings

from .base import (
    APIError,
    AuthenticationError,
    ModelClient,
    ModelError,
    RateLimitError,
)
from .claude import ClaudeClient
from .gemini import GeminiClient
from .gpt import GPTClient
from .grok import GrokClient
from .tools import (
    DEFAULT_TOOLS,
    ToolDefinition,
    ToolParameter,
    tools_to_anthropic,
    tools_to_google,
    tools_to_openai,
    tools_to_xai,
)
from .types import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ShouldSpeakResult,
    StreamChunk,
    ToolCall,
    ToolResult,
    Usage,
)

logger = logging.getLogger(__name__)

# Registry mapping model names to client classes
MODEL_CLIENTS: dict[str, Type[ModelClient]] = {
    "claude": ClaudeClient,
    "gpt": GPTClient,
    "gemini": GeminiClient,
    "grok": GrokClient,
}

# Model colors for UI
MODEL_COLORS: dict[str, str] = {
    "claude": "#E07B53",
    "gpt": "#10A37F",
    "gemini": "#4285F4",
    "grok": "#7C3AED",
}

# Model display names
MODEL_DISPLAY_NAMES: dict[str, str] = {
    "claude": "Claude",
    "gpt": "GPT",
    "gemini": "Gemini",
    "grok": "Grok",
}


def get_client(
    name: str,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> ModelClient:
    """Create a model client by name.

    Args:
        name: Model name ('claude', 'gpt', 'gemini', 'grok')
        api_key: Optional API key (falls back to environment variable)
        model_id: Optional model ID (uses default if not provided)
        max_tokens: Optional max tokens
        temperature: Optional temperature

    Returns:
        Initialized ModelClient instance

    Raises:
        ValueError: If model name is not recognized
    """
    if name not in MODEL_CLIENTS:
        raise ValueError(
            f"Unknown model: {name}. Available models: {list(MODEL_CLIENTS.keys())}"
        )

    client_class = MODEL_CLIENTS[name]

    kwargs = {}
    if api_key is not None:
        kwargs["api_key"] = api_key
    if model_id is not None:
        kwargs["model_id"] = model_id
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature

    return client_class(**kwargs)


def get_client_from_settings(name: str, settings: Optional[Settings] = None) -> ModelClient:
    """Create a model client using settings.

    Args:
        name: Model name
        settings: Optional settings (uses global settings if not provided)

    Returns:
        Initialized ModelClient instance
    """
    if settings is None:
        settings = get_settings()

    # Get model-specific config
    model_config = getattr(settings.models, name, None)
    if model_config is None:
        raise ValueError(f"No configuration found for model: {name}")

    # Get API key
    api_key_map = {
        "claude": settings.anthropic_api_key,
        "gpt": settings.openai_api_key,
        "gemini": settings.google_api_key,
        "grok": settings.xai_api_key,
    }
    api_key = api_key_map.get(name)

    return get_client(
        name=name,
        api_key=api_key,
        model_id=model_config.model_id,
        max_tokens=model_config.max_tokens,
        temperature=model_config.temperature,
    )


def get_all_clients(settings: Optional[Settings] = None) -> dict[str, ModelClient]:
    """Create all model clients.

    Args:
        settings: Optional settings

    Returns:
        Dictionary of model name to client
    """
    clients = {}
    for name in MODEL_CLIENTS.keys():
        try:
            clients[name] = get_client_from_settings(name, settings)
        except Exception as e:
            logger.warning(f"Failed to initialize {name} client: {e}")
    return clients


def get_enabled_clients(settings: Optional[Settings] = None) -> dict[str, ModelClient]:
    """Create clients for enabled models only.

    Args:
        settings: Optional settings

    Returns:
        Dictionary of enabled model name to client
    """
    if settings is None:
        settings = get_settings()

    clients = {}
    for name in MODEL_CLIENTS.keys():
        model_config = getattr(settings.models, name, None)
        if model_config and model_config.enabled:
            try:
                client = get_client_from_settings(name, settings)
                if client.is_available:
                    clients[name] = client
                else:
                    logger.info(f"Model {name} is enabled but not available (missing API key)")
            except Exception as e:
                logger.warning(f"Failed to initialize {name} client: {e}")

    return clients


def get_available_clients(settings: Optional[Settings] = None) -> dict[str, ModelClient]:
    """Create clients for available models (enabled + has API key).

    This is the recommended function for getting clients that are ready to use.

    Args:
        settings: Optional settings

    Returns:
        Dictionary of available model name to client
    """
    return get_enabled_clients(settings)


__all__ = [
    # Base classes and errors
    "ModelClient",
    "ModelError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    # Client implementations
    "ClaudeClient",
    "GPTClient",
    "GeminiClient",
    "GrokClient",
    # Types
    "Message",
    "MessageRole",
    "ModelResponse",
    "StreamChunk",
    "ShouldSpeakResult",
    "ToolCall",
    "ToolResult",
    "Usage",
    "FinishReason",
    # Tools
    "ToolDefinition",
    "ToolParameter",
    "DEFAULT_TOOLS",
    "tools_to_anthropic",
    "tools_to_openai",
    "tools_to_google",
    "tools_to_xai",
    # Registry functions
    "get_client",
    "get_client_from_settings",
    "get_all_clients",
    "get_enabled_clients",
    "get_available_clients",
    # Constants
    "MODEL_CLIENTS",
    "MODEL_COLORS",
    "MODEL_DISPLAY_NAMES",
]
