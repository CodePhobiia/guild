"""Unified message and response types for all model providers."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageRole(str, Enum):
    """Role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class FinishReason(str, Enum):
    """Reason why the model stopped generating."""

    STOP = "stop"
    TOOL_USE = "tool_use"
    LENGTH = "length"
    ERROR = "error"
    CONTENT_FILTER = "content_filter"


@dataclass
class ToolCall:
    """A tool call made by an AI model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result from executing a tool."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """A message in a conversation."""

    role: MessageRole
    content: str
    name: Optional[str] = None  # For tool messages, the tool name
    model: Optional[str] = None  # Which model generated this (for assistant messages)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str, model: Optional[str] = None) -> "Message":
        """Create an assistant message."""
        return cls(role=MessageRole.ASSISTANT, content=content, model=model)

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str, is_error: bool = False) -> "Message":
        """Create a tool result message for a single tool call."""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            name=name,
            tool_results=[ToolResult(tool_call_id=tool_call_id, content=content, is_error=is_error)],
        )

    @classmethod
    def tool_results(cls, results: list["ToolResult"]) -> "Message":
        """Create a tool result message for multiple tool results.

        Args:
            results: List of ToolResult objects.

        Returns:
            Message with role=TOOL containing all tool results.
        """
        # Combine contents for the main content field
        content = "\n\n".join(
            f"[{r.tool_call_id}]: {r.content}" for r in results
        )
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_results=results,
        )

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == MessageRole.USER

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == MessageRole.ASSISTANT


@dataclass
class Usage:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: Optional[float] = None

    def __add__(self, other: "Usage") -> "Usage":
        """Add two usage objects together."""
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost_estimate=(
                (self.cost_estimate or 0) + (other.cost_estimate or 0)
                if self.cost_estimate is not None or other.cost_estimate is not None
                else None
            ),
        )


@dataclass
class ModelResponse:
    """Response from an AI model."""

    content: str
    model: str
    finish_reason: FinishReason
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Optional[Usage] = None
    raw_response: Optional[Any] = None  # Original provider response for debugging

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    content: str = ""
    is_complete: bool = False
    tool_call: Optional[ToolCall] = None
    finish_reason: Optional[FinishReason] = None
    usage: Optional[Usage] = None


@dataclass
class ShouldSpeakResult:
    """Result from a model deciding whether to speak."""

    should_speak: bool
    confidence: float  # 0.0 to 1.0
    reason: str = ""

    @classmethod
    def yes(cls, confidence: float = 1.0, reason: str = "") -> "ShouldSpeakResult":
        """Create a 'should speak' result."""
        return cls(should_speak=True, confidence=confidence, reason=reason)

    @classmethod
    def no(cls, confidence: float = 1.0, reason: str = "") -> "ShouldSpeakResult":
        """Create a 'should not speak' result."""
        return cls(should_speak=False, confidence=confidence, reason=reason)


# Cost per million tokens for various models (approximate)
MODEL_COSTS = {
    # Claude models (input/output per million tokens)
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.25, 1.25),
    # GPT models
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4-turbo": (10.0, 30.0),
    # Gemini models
    "gemini-2.0-flash": (0.075, 0.3),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.3),
    # Grok models (estimated)
    "grok-3": (3.0, 15.0),
    "grok-2": (2.0, 10.0),
}


def estimate_cost(model_id: str, usage: Usage) -> float:
    """Estimate cost based on model and usage."""
    if model_id not in MODEL_COSTS:
        return 0.0

    input_cost, output_cost = MODEL_COSTS[model_id]
    cost = (usage.prompt_tokens / 1_000_000 * input_cost) + (
        usage.completion_tokens / 1_000_000 * output_cost
    )
    return round(cost, 6)
