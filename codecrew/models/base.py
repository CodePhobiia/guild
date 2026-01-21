"""Abstract base class for model clients."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, AsyncIterator, Callable, Optional, TypeVar

from .tools import ToolDefinition
from .types import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ShouldSpeakResult,
    StreamChunk,
    Usage,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ModelError(Exception):
    """Base exception for model errors."""

    pass


class RateLimitError(ModelError):
    """Raised when rate limited by the API."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(ModelError):
    """Raised when authentication fails."""

    pass


class APIError(ModelError):
    """Raised for general API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (RateLimitError, APIError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types that trigger retries
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        break

                    # Use retry_after if available
                    if isinstance(e, RateLimitError) and e.retry_after:
                        wait_time = e.retry_after
                    else:
                        wait_time = min(delay, max_delay)
                        delay *= exponential_base

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)

            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


# The "should I speak?" prompt template
SHOULD_SPEAK_PROMPT = """You are {model_name} in a group coding chat with other AI assistants.

Current conversation:
{conversation_history}

The user's latest message:
{user_message}

Other models that have already responded:
{previous_responses}

Should you respond? Consider:
1. Do you have a genuinely different perspective?
2. Is there an error or important caveat to address?
3. Can you add meaningful value beyond what's been said?
4. Were you directly addressed or @mentioned?

Respond with ONLY a JSON object (no markdown, no explanation):
{{"should_speak": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""


class ModelClient(ABC):
    """Abstract base class for AI model clients.

    All model clients must implement this interface to ensure
    consistent behavior across different providers.
    """

    # Class attributes - must be set by subclasses
    name: str  # 'claude', 'gpt', 'gemini', 'grok'
    display_name: str  # 'Claude', 'GPT', etc.
    color: str  # Hex color for UI

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Initialize the model client.

        Args:
            api_key: API key for the provider (falls back to env var)
            model_id: Model identifier to use
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation
        """
        self.api_key = api_key
        self.model_id = model_id or self._default_model_id()
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    def _default_model_id(self) -> str:
        """Return the default model ID for this provider."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model is available (API key configured, etc.)."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Generate a response from the model.

        Args:
            messages: Conversation history
            tools: Optional list of tools the model can use
            max_tokens: Override default max tokens
            temperature: Override default temperature
            system: System prompt

        Returns:
            ModelResponse with generated content
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response from the model.

        Args:
            messages: Conversation history
            tools: Optional list of tools the model can use
            max_tokens: Override default max tokens
            temperature: Override default temperature
            system: System prompt

        Yields:
            StreamChunk objects as content is generated
        """
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        ...

    async def should_speak(
        self,
        conversation: list[Message],
        user_message: str,
        previous_responses: list[ModelResponse],
        was_mentioned: bool = False,
    ) -> ShouldSpeakResult:
        """Determine if this model should respond.

        Uses a meta-prompt to ask the model whether it has something
        valuable to contribute to the conversation.

        Args:
            conversation: Full conversation history
            user_message: The user's latest message
            previous_responses: Responses from other models in this turn
            was_mentioned: Whether this model was @mentioned

        Returns:
            ShouldSpeakResult with decision and confidence
        """
        # If directly mentioned, always speak
        if was_mentioned:
            return ShouldSpeakResult.yes(confidence=1.0, reason="Directly mentioned")

        # Format conversation history
        history_lines = []
        for msg in conversation[-10:]:  # Last 10 messages for context
            role = msg.model or msg.role.value
            history_lines.append(f"{role}: {msg.content[:500]}...")

        # Format previous responses
        prev_lines = []
        for resp in previous_responses:
            prev_lines.append(f"{resp.model}: {resp.content[:500]}...")

        prompt = SHOULD_SPEAK_PROMPT.format(
            model_name=self.display_name,
            conversation_history="\n".join(history_lines) or "(No previous messages)",
            user_message=user_message,
            previous_responses="\n".join(prev_lines) or "(None yet)",
        )

        try:
            response = await self.generate(
                messages=[Message.user(prompt)],
                max_tokens=150,
                temperature=0.3,  # Lower temperature for more consistent decisions
            )

            # Parse JSON response
            result = self._parse_should_speak_response(response.content)
            return result

        except Exception as e:
            logger.warning(f"Error in should_speak for {self.name}: {e}")
            # Default to speaking if we can't determine
            return ShouldSpeakResult.yes(confidence=0.5, reason=f"Error determining: {e}")

    def _parse_should_speak_response(self, content: str) -> ShouldSpeakResult:
        """Parse the JSON response from should_speak evaluation."""
        # Try to extract JSON from response
        content = content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            data = json.loads(content)
            return ShouldSpeakResult(
                should_speak=bool(data.get("should_speak", True)),
                confidence=float(data.get("confidence", 0.5)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse should_speak response: {content[:100]}... Error: {e}")
            # Default to speaking if we can't parse
            return ShouldSpeakResult.yes(confidence=0.5, reason="Could not parse response")

    def _format_messages_for_logging(self, messages: list[Message]) -> str:
        """Format messages for debug logging."""
        lines = []
        for msg in messages:
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            lines.append(f"  [{msg.role.value}]: {content_preview}")
        return "\n".join(lines)

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars per token average).

        Subclasses should override with more accurate counting.
        """
        return len(text) // 4
