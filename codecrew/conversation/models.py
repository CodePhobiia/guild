"""Data models for conversation entities."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


class ToolCall(BaseModel):
    """A tool call made by an AI model."""

    id: str
    message_id: str
    tool_name: str
    parameters: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    status: ToolCallStatus = ToolCallStatus.PENDING
    executed_at: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: dict) -> "ToolCall":
        """Create a ToolCall from a database row."""
        import json

        return cls(
            id=row["id"],
            message_id=row["message_id"],
            tool_name=row["tool_name"],
            parameters=json.loads(row["parameters"]) if row["parameters"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
            status=ToolCallStatus(row["status"]) if row["status"] else ToolCallStatus.PENDING,
            executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
        )


class Message(BaseModel):
    """A message in a conversation."""

    id: str
    session_id: str
    role: MessageRole
    content: str
    model: Optional[str] = None  # The AI model that generated this message
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    is_pinned: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: dict, tool_calls: Optional[list[dict]] = None) -> "Message":
        """Create a Message from a database row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            model=row["model"],
            tokens_used=row["tokens_used"],
            cost_estimate=row["cost_estimate"],
            is_pinned=bool(row["is_pinned"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            tool_calls=[ToolCall.from_db_row(tc) for tc in (tool_calls or [])],
        )

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == MessageRole.USER

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == MessageRole.ASSISTANT


class Session(BaseModel):
    """A conversation session."""

    id: str
    name: Optional[str] = None
    project_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict[str, Any]] = None
    messages: list[Message] = Field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: dict, messages: Optional[list[Message]] = None) -> "Session":
        """Create a Session from a database row."""
        import json

        return cls(
            id=row["id"],
            name=row["name"],
            project_path=row["project_path"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            messages=messages or [],
        )

    @property
    def message_count(self) -> int:
        """Get the number of messages in this session."""
        return len(self.messages)

    @property
    def display_name(self) -> str:
        """Get a display name for this session."""
        if self.name:
            return self.name
        return f"Session {self.id[:8]}"


class ModelResponse(BaseModel):
    """Response from an AI model."""

    model: str
    content: str
    should_speak: bool = True
    confidence: float = 1.0
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_silent(self) -> bool:
        """Check if the model chose to stay silent."""
        return not self.should_speak

    @property
    def has_error(self) -> bool:
        """Check if there was an error."""
        return self.error is not None


class SpeakingDecision(BaseModel):
    """Decision from a model about whether to speak."""

    model: str
    should_speak: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None


class ConversationContext(BaseModel):
    """Context assembled for a model to generate a response."""

    session_id: str
    messages: list[Message]
    pinned_messages: list[Message] = Field(default_factory=list)
    current_user_message: str
    previous_responses: list[ModelResponse] = Field(default_factory=list)
    mentioned_models: list[str] = Field(default_factory=list)
    is_direct_mention: bool = False
    project_path: Optional[str] = None

    @property
    def total_messages(self) -> int:
        """Get total number of context messages."""
        return len(self.messages) + len(self.pinned_messages)
