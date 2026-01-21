"""Orchestrator event types.

Events are yielded by the orchestrator to communicate state changes
to the UI layer during message processing.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from codecrew.models.types import ModelResponse, ToolCall, ToolResult, Usage


class EventType(Enum):
    """Types of events emitted by the orchestrator."""

    # Evaluation phase
    THINKING = auto()  # Starting to evaluate which models should speak
    EVALUATING = auto()  # Evaluating a specific model

    # Decision phase
    WILL_SPEAK = auto()  # Model decided to speak
    WILL_STAY_SILENT = auto()  # Model decided to stay silent

    # Response generation phase
    RESPONSE_START = auto()  # Model starting to generate response
    RESPONSE_CHUNK = auto()  # Streaming chunk received
    RESPONSE_COMPLETE = auto()  # Full response ready

    # Tool use phase
    TOOL_CALL = auto()  # Model wants to call a tool
    TOOL_EXECUTING = auto()  # Tool is being executed
    TOOL_RESULT = auto()  # Tool execution completed
    TOOL_PERMISSION_REQUEST = auto()  # Tool requires permission

    # Completion/error phase
    ERROR = auto()  # Error occurred
    TURN_COMPLETE = auto()  # All models done for this turn


@dataclass
class SpeakerDecision:
    """Result of evaluating whether a model should speak."""

    model: str
    should_speak: bool
    confidence: float
    reason: str
    is_forced: bool = False  # True if @mentioned

    @classmethod
    def forced(cls, model: str, reason: str = "Directly mentioned") -> "SpeakerDecision":
        """Create a forced speaker decision from @mention."""
        return cls(
            model=model,
            should_speak=True,
            confidence=1.0,
            reason=reason,
            is_forced=True,
        )

    @classmethod
    def speak(
        cls, model: str, confidence: float, reason: str
    ) -> "SpeakerDecision":
        """Create a 'will speak' decision."""
        return cls(
            model=model,
            should_speak=True,
            confidence=confidence,
            reason=reason,
        )

    @classmethod
    def silent(
        cls, model: str, confidence: float, reason: str
    ) -> "SpeakerDecision":
        """Create a 'will stay silent' decision."""
        return cls(
            model=model,
            should_speak=False,
            confidence=confidence,
            reason=reason,
        )


@dataclass
class OrchestratorEvent:
    """Event emitted by the orchestrator during message processing.

    The type field determines which other fields are populated:
    - THINKING: Just the type
    - EVALUATING: model
    - WILL_SPEAK/WILL_STAY_SILENT: model, decision
    - RESPONSE_START: model
    - RESPONSE_CHUNK: model, content
    - RESPONSE_COMPLETE: model, response
    - TOOL_CALL: model, tool_call
    - TOOL_EXECUTING: model, tool_call
    - TOOL_RESULT: model, tool_result
    - TOOL_PERMISSION_REQUEST: model, tool_call, permission_request
    - ERROR: model (optional), error
    - TURN_COMPLETE: usage (aggregated), responses
    """

    type: EventType
    model: Optional[str] = None
    content: Optional[str] = None
    response: Optional[ModelResponse] = None
    decision: Optional[SpeakerDecision] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    error: Optional[str] = None
    usage: Optional[Usage] = None
    responses: list[ModelResponse] = field(default_factory=list)
    # Tool permission request (for TOOL_PERMISSION_REQUEST events)
    permission_request: Optional[Any] = None  # PermissionRequest from tools module

    @classmethod
    def thinking(cls) -> "OrchestratorEvent":
        """Create a THINKING event."""
        return cls(type=EventType.THINKING)

    @classmethod
    def evaluating(cls, model: str) -> "OrchestratorEvent":
        """Create an EVALUATING event."""
        return cls(type=EventType.EVALUATING, model=model)

    @classmethod
    def will_speak(cls, decision: SpeakerDecision) -> "OrchestratorEvent":
        """Create a WILL_SPEAK event."""
        return cls(
            type=EventType.WILL_SPEAK,
            model=decision.model,
            decision=decision,
        )

    @classmethod
    def will_stay_silent(cls, decision: SpeakerDecision) -> "OrchestratorEvent":
        """Create a WILL_STAY_SILENT event."""
        return cls(
            type=EventType.WILL_STAY_SILENT,
            model=decision.model,
            decision=decision,
        )

    @classmethod
    def response_start(cls, model: str) -> "OrchestratorEvent":
        """Create a RESPONSE_START event."""
        return cls(type=EventType.RESPONSE_START, model=model)

    @classmethod
    def response_chunk(cls, model: str, content: str) -> "OrchestratorEvent":
        """Create a RESPONSE_CHUNK event."""
        return cls(type=EventType.RESPONSE_CHUNK, model=model, content=content)

    @classmethod
    def response_complete(
        cls, model: str, response: ModelResponse
    ) -> "OrchestratorEvent":
        """Create a RESPONSE_COMPLETE event."""
        return cls(type=EventType.RESPONSE_COMPLETE, model=model, response=response)

    @classmethod
    def tool_call_event(cls, model: str, tool_call: ToolCall) -> "OrchestratorEvent":
        """Create a TOOL_CALL event."""
        return cls(type=EventType.TOOL_CALL, model=model, tool_call=tool_call)

    @classmethod
    def tool_executing_event(
        cls, model: str, tool_call: ToolCall
    ) -> "OrchestratorEvent":
        """Create a TOOL_EXECUTING event."""
        return cls(type=EventType.TOOL_EXECUTING, model=model, tool_call=tool_call)

    @classmethod
    def tool_result_event(
        cls, model: str, tool_result: ToolResult
    ) -> "OrchestratorEvent":
        """Create a TOOL_RESULT event."""
        return cls(type=EventType.TOOL_RESULT, model=model, tool_result=tool_result)

    @classmethod
    def tool_permission_request_event(
        cls,
        model: str,
        tool_call: ToolCall,
        permission_request: Any,
    ) -> "OrchestratorEvent":
        """Create a TOOL_PERMISSION_REQUEST event."""
        return cls(
            type=EventType.TOOL_PERMISSION_REQUEST,
            model=model,
            tool_call=tool_call,
            permission_request=permission_request,
        )

    @classmethod
    def error_event(
        cls, error: str, model: Optional[str] = None
    ) -> "OrchestratorEvent":
        """Create an ERROR event."""
        return cls(type=EventType.ERROR, model=model, error=error)

    @classmethod
    def turn_complete(
        cls,
        responses: list[ModelResponse],
        usage: Optional[Usage] = None,
    ) -> "OrchestratorEvent":
        """Create a TURN_COMPLETE event."""
        return cls(
            type=EventType.TURN_COMPLETE,
            responses=responses,
            usage=usage,
        )
