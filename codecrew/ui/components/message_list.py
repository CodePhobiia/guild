"""Message list component for displaying conversation history."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.panel import Panel
from rich.text import Text

from codecrew.models.types import Message, ModelResponse, ToolCall, ToolResult, Usage
from codecrew.ui.components.message import (
    DecisionIndicator,
    MessageRenderer,
    StreamingMessage,
)
from codecrew.ui.components.spinner import (
    ThinkingIndicator,
    ToolExecutingIndicator,
    TypingIndicator,
)
from codecrew.ui.theme import Theme


@dataclass
class MessageItem:
    """A single item in the message list.

    Can represent a user message, assistant message, system message,
    tool call, tool result, or status indicator.
    """

    type: str  # user, assistant, system, tool_call, tool_result, thinking, typing
    content: str = ""
    model: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    usage: Optional[Usage] = None
    is_pinned: bool = False
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    execution_time: Optional[float] = None
    # For decisions
    will_speak: Optional[bool] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    is_forced: bool = False
    # For thinking/typing indicators
    models: list[str] = field(default_factory=list)
    tool_name: Optional[str] = None

    @classmethod
    def user(cls, content: str) -> "MessageItem":
        """Create a user message item."""
        return cls(type="user", content=content)

    @classmethod
    def assistant(
        cls,
        content: str,
        model: str,
        usage: Optional[Usage] = None,
        is_pinned: bool = False,
    ) -> "MessageItem":
        """Create an assistant message item."""
        return cls(
            type="assistant",
            content=content,
            model=model,
            usage=usage,
            is_pinned=is_pinned,
        )

    @classmethod
    def system(cls, content: str) -> "MessageItem":
        """Create a system message item."""
        return cls(type="system", content=content)

    @classmethod
    def error(cls, error: str, model: Optional[str] = None) -> "MessageItem":
        """Create an error message item."""
        return cls(type="error", content=error, model=model)

    @classmethod
    def from_tool_call(cls, tool_call: ToolCall, model: str) -> "MessageItem":
        """Create a tool call item."""
        return cls(type="tool_call", model=model, tool_call=tool_call)

    @classmethod
    def from_tool_result(
        cls,
        tool_result: ToolResult,
        execution_time: Optional[float] = None,
    ) -> "MessageItem":
        """Create a tool result item."""
        return cls(
            type="tool_result",
            tool_result=tool_result,
            execution_time=execution_time,
        )

    @classmethod
    def thinking(cls, models: list[str]) -> "MessageItem":
        """Create a thinking indicator item."""
        return cls(type="thinking", models=models)

    @classmethod
    def typing(cls, model: str) -> "MessageItem":
        """Create a typing indicator item."""
        return cls(type="typing", model=model)

    @classmethod
    def tool_executing(cls, tool_name: str, model: str) -> "MessageItem":
        """Create a tool executing indicator item."""
        return cls(type="tool_executing", model=model, tool_name=tool_name)

    @classmethod
    def decision(
        cls,
        model: str,
        will_speak: bool,
        confidence: float,
        reason: str,
        is_forced: bool = False,
    ) -> "MessageItem":
        """Create a decision indicator item."""
        return cls(
            type="decision",
            model=model,
            will_speak=will_speak,
            confidence=confidence,
            reason=reason,
            is_forced=is_forced,
        )


class MessageList:
    """Manages and renders a list of conversation messages.

    Handles both static messages and dynamic streaming updates.
    """

    def __init__(
        self,
        theme: Theme,
        code_theme: str = "monokai",
        use_unicode: bool = True,
        show_timestamps: bool = False,
        show_decisions: bool = False,
        max_messages: Optional[int] = None,
    ):
        """Initialize the message list.

        Args:
            theme: Theme for styling
            code_theme: Code syntax highlighting theme
            use_unicode: Whether to use Unicode characters
            show_timestamps: Whether to show message timestamps
            show_decisions: Whether to show model speaking decisions
            max_messages: Maximum messages to keep (None for unlimited)
        """
        self.theme = theme
        self.code_theme = code_theme
        self.use_unicode = use_unicode
        self.show_timestamps = show_timestamps
        self.show_decisions = show_decisions
        self.max_messages = max_messages

        self._items: list[MessageItem] = []
        self._streaming: Optional[StreamingMessage] = None
        self._thinking: Optional[ThinkingIndicator] = None
        self._typing: Optional[TypingIndicator] = None
        self._tool_executing: Optional[ToolExecutingIndicator] = None

        self._renderer = MessageRenderer(
            theme=theme,
            code_theme=code_theme,
            use_unicode=use_unicode,
            show_timestamps=show_timestamps,
        )

    def add(self, item: MessageItem) -> None:
        """Add a message item to the list.

        Args:
            item: Message item to add
        """
        self._items.append(item)

        # Enforce max messages limit
        if self.max_messages and len(self._items) > self.max_messages:
            self._items = self._items[-self.max_messages :]

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add(MessageItem.user(content))

    def add_assistant_message(
        self,
        content: str,
        model: str,
        usage: Optional[Usage] = None,
        is_pinned: bool = False,
    ) -> None:
        """Add an assistant message."""
        self.add(MessageItem.assistant(content, model, usage, is_pinned))

    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self.add(MessageItem.system(content))

    def add_error(self, error: str, model: Optional[str] = None) -> None:
        """Add an error message."""
        self.add(MessageItem.error(error, model))

    def add_tool_call(self, tool_call: ToolCall, model: str) -> None:
        """Add a tool call."""
        self.add(MessageItem.from_tool_call(tool_call, model))

    def add_tool_result(
        self,
        tool_result: ToolResult,
        execution_time: Optional[float] = None,
    ) -> None:
        """Add a tool result."""
        self.add(MessageItem.from_tool_result(tool_result, execution_time))

    def add_decision(
        self,
        model: str,
        will_speak: bool,
        confidence: float,
        reason: str,
        is_forced: bool = False,
    ) -> None:
        """Add a speaking decision (only if show_decisions is True)."""
        if self.show_decisions:
            self.add(MessageItem.decision(model, will_speak, confidence, reason, is_forced))

    def start_thinking(self, models: list[str]) -> None:
        """Show thinking indicator.

        Args:
            models: List of models being evaluated
        """
        self._thinking = ThinkingIndicator(
            models=models,
            theme=self.theme,
            use_unicode=self.use_unicode,
        )

    def stop_thinking(self) -> None:
        """Hide thinking indicator."""
        self._thinking = None

    def start_typing(self, model: str) -> None:
        """Show typing indicator for a model.

        Args:
            model: Model that is typing
        """
        self._typing = TypingIndicator(
            model=model,
            theme=self.theme,
            use_unicode=self.use_unicode,
        )

    def stop_typing(self) -> None:
        """Hide typing indicator."""
        self._typing = None

    def start_tool_executing(self, tool_name: str, model: str) -> None:
        """Show tool executing indicator.

        Args:
            tool_name: Name of the tool being executed
            model: Model that requested the tool
        """
        self._tool_executing = ToolExecutingIndicator(
            tool_name=tool_name,
            model=model,
            theme=self.theme,
            use_unicode=self.use_unicode,
        )

    def stop_tool_executing(self) -> None:
        """Hide tool executing indicator."""
        self._tool_executing = None

    def start_streaming(self, model: str) -> StreamingMessage:
        """Start streaming a response.

        Args:
            model: Model generating the response

        Returns:
            StreamingMessage instance to append chunks to
        """
        self.stop_typing()
        self._streaming = StreamingMessage(
            model=model,
            theme=self.theme,
            code_theme=self.code_theme,
            use_unicode=self.use_unicode,
        )
        return self._streaming

    def finish_streaming(self, response: ModelResponse) -> None:
        """Finish streaming and add the complete message.

        Args:
            response: Complete model response
        """
        if self._streaming:
            self._streaming.complete(response)
            # Add as regular message
            self.add_assistant_message(
                content=response.content,
                model=self._streaming.model,
                usage=response.usage,
            )
            self._streaming = None

    def clear(self) -> None:
        """Clear all messages."""
        self._items.clear()
        self._streaming = None
        self._thinking = None
        self._typing = None
        self._tool_executing = None

    def clear_indicators(self) -> None:
        """Clear all status indicators."""
        self._thinking = None
        self._typing = None
        self._tool_executing = None

    @property
    def message_count(self) -> int:
        """Get the number of messages (excluding indicators)."""
        return len(self._items)

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming a response."""
        return self._streaming is not None

    def _render_item(self, item: MessageItem) -> Panel | Text:
        """Render a single message item.

        Args:
            item: Message item to render

        Returns:
            Rendered Rich object
        """
        if item.type == "user":
            return self._renderer.render_user_message(item.content, item.timestamp)
        elif item.type == "assistant":
            return self._renderer.render_assistant_message(
                content=item.content,
                model=item.model or "assistant",
                usage=item.usage,
                timestamp=item.timestamp,
                is_pinned=item.is_pinned,
            )
        elif item.type == "system":
            return self._renderer.render_system_message(item.content, item.timestamp)
        elif item.type == "error":
            return self._renderer.render_error_message(item.content, item.model)
        elif item.type == "tool_call" and item.tool_call:
            return self._renderer.render_tool_call(item.tool_call, item.model or "assistant")
        elif item.type == "tool_result" and item.tool_result:
            return self._renderer.render_tool_result(item.tool_result, item.execution_time)
        elif item.type == "decision":
            return DecisionIndicator(
                model=item.model or "",
                will_speak=item.will_speak or False,
                confidence=item.confidence or 0.0,
                reason=item.reason or "",
                is_forced=item.is_forced,
                theme=self.theme,
                use_unicode=self.use_unicode,
            ).render()
        else:
            # Fallback
            return Text(str(item.content))

    def render(self) -> Group:
        """Render the complete message list.

        Returns:
            Group containing all rendered messages
        """
        renderables = []

        # Render all static messages
        for item in self._items:
            renderables.append(self._render_item(item))

        # Render streaming message if active
        if self._streaming and not self._streaming.is_complete:
            renderables.append(self._streaming.render())

        # Render status indicators
        if self._thinking:
            renderables.append(self._thinking.render())
        if self._typing:
            renderables.append(self._typing.render())
        if self._tool_executing:
            renderables.append(self._tool_executing.render())

        return Group(*renderables)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()
