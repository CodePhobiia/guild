"""Message rendering components."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from codecrew.models.types import ModelResponse, ToolCall, ToolResult, Usage
from codecrew.ui.theme import (
    Theme,
    get_model_display_name,
    get_symbol,
)


@dataclass
class MessageRenderer:
    """Renders individual messages with proper styling.

    Handles rendering of user messages, assistant responses,
    system messages, and tool-related messages.
    """

    theme: Theme
    code_theme: str = "monokai"
    use_unicode: bool = True
    show_timestamps: bool = False
    max_width: Optional[int] = None

    def render_user_message(
        self,
        content: str,
        timestamp: Optional[datetime] = None,
    ) -> Panel:
        """Render a user message.

        Args:
            content: Message content
            timestamp: Optional timestamp

        Returns:
            Panel containing the rendered message
        """
        text = Text(content, style=self.theme.get_message_style("user"))

        title = self._build_title("You", None, timestamp)

        return Panel(
            text,
            title=title,
            title_align="left",
            border_style=self.theme.get_model_color("user"),
            padding=(0, 1),
        )

    def render_assistant_message(
        self,
        content: str,
        model: str,
        usage: Optional[Usage] = None,
        timestamp: Optional[datetime] = None,
        is_pinned: bool = False,
    ) -> Panel:
        """Render an assistant message with markdown support.

        Args:
            content: Message content (markdown)
            model: Model name (claude, gpt, etc.)
            usage: Optional token usage info
            timestamp: Optional timestamp
            is_pinned: Whether the message is pinned

        Returns:
            Panel containing the rendered message
        """
        # Render markdown content
        markdown = Markdown(
            content,
            code_theme=self.code_theme,
        )

        # Build title with model name and optional usage
        title = self._build_title(
            get_model_display_name(model),
            model,
            timestamp,
            usage,
            is_pinned,
        )

        return Panel(
            markdown,
            title=title,
            title_align="left",
            border_style=self.theme.get_model_color(model),
            padding=(0, 1),
        )

    def render_system_message(
        self,
        content: str,
        timestamp: Optional[datetime] = None,
    ) -> Panel:
        """Render a system message.

        Args:
            content: Message content
            timestamp: Optional timestamp

        Returns:
            Panel containing the rendered message
        """
        text = Text(content, style=self.theme.get_message_style("system"))

        title = self._build_title("System", None, timestamp)

        return Panel(
            text,
            title=title,
            title_align="left",
            border_style=self.theme.get_model_color("system"),
            padding=(0, 1),
        )

    def render_error_message(
        self,
        error: str,
        model: Optional[str] = None,
    ) -> Panel:
        """Render an error message.

        Args:
            error: Error message
            model: Optional model that caused the error

        Returns:
            Panel containing the error
        """
        text = Text()
        text.append(get_symbol("error", self.use_unicode), style="red bold")
        text.append(" ")
        text.append(error, style=self.theme.get_message_style("error"))

        source = get_model_display_name(model) if model else "Error"

        return Panel(
            text,
            title=f"[red bold]{source}[/red bold]",
            title_align="left",
            border_style="red",
            padding=(0, 1),
        )

    def render_tool_call(
        self,
        tool_call: ToolCall,
        model: str,
    ) -> Panel:
        """Render a tool call request.

        Args:
            tool_call: The tool call
            model: Model that made the call

        Returns:
            Panel containing the tool call details
        """
        text = Text()

        # Tool name
        text.append(get_symbol("tool", self.use_unicode), style="yellow")
        text.append(" ")
        text.append(tool_call.name, style="bold yellow")
        text.append("\n")

        # Arguments
        if tool_call.arguments:
            text.append("\nArguments:\n", style="dim")
            for key, value in tool_call.arguments.items():
                text.append(f"  {key}: ", style="cyan")
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                text.append(f"{str_value}\n")

        title_text = Text()
        model_style = self.theme.get_model_style(model)
        title_text.append(get_model_display_name(model), style=model_style)
        title_text.append(" calling tool")

        return Panel(
            text,
            title=title_text,
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        )

    def render_tool_result(
        self,
        tool_result: ToolResult,
        execution_time: Optional[float] = None,
    ) -> Panel:
        """Render a tool result.

        Args:
            tool_result: The tool result
            execution_time: Optional execution time in seconds

        Returns:
            Panel containing the tool result
        """
        # Determine if success or error
        is_error = tool_result.is_error

        text = Text()

        # Status indicator
        if is_error:
            text.append(get_symbol("error", self.use_unicode), style="red bold")
            text.append(" Error", style="red bold")
        else:
            text.append(get_symbol("complete", self.use_unicode), style="green")
            text.append(" Success", style="green")

        # Execution time
        if execution_time is not None:
            text.append(f" ({execution_time:.2f}s)", style="dim")

        text.append("\n")

        # Result content
        content = tool_result.content
        if isinstance(content, str):
            # Check if it looks like code
            if content.startswith("```") or "\n" in content and len(content) > 200:
                # Try to render as syntax-highlighted code
                text.append("\n")
                # Just show as text for now - could enhance with Syntax
                if len(content) > 500:
                    content = content[:497] + "..."
                text.append(content, style="dim")
            else:
                if len(content) > 300:
                    content = content[:297] + "..."
                text.append(content)
        else:
            text.append(str(content))

        border_style = "red" if is_error else "green"

        return Panel(
            text,
            title="Tool Result",
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )

    def _build_title(
        self,
        name: str,
        model: Optional[str],
        timestamp: Optional[datetime],
        usage: Optional[Usage] = None,
        is_pinned: bool = False,
    ) -> Text:
        """Build a panel title with optional metadata.

        Args:
            name: Display name
            model: Model for color styling
            timestamp: Optional timestamp
            usage: Optional token usage
            is_pinned: Whether message is pinned

        Returns:
            Formatted title Text
        """
        title = Text()

        # Pin indicator
        if is_pinned:
            title.append(get_symbol("pin", self.use_unicode), style="yellow")
            title.append(" ")

        # Name with model color
        if model:
            title.append(name, style=self.theme.get_model_style(model))
        else:
            title.append(name, style="bold")

        # Usage info
        if usage and usage.total_tokens:
            title.append(f" ({usage.total_tokens} tokens)", style="dim")

        # Timestamp
        if self.show_timestamps and timestamp:
            title.append(f" {timestamp.strftime('%H:%M')}", style="dim")

        return title


@dataclass
class StreamingMessage:
    """Handles real-time streaming of message content.

    Accumulates chunks and provides efficient rendering updates
    during streaming responses.
    """

    model: str
    theme: Theme
    code_theme: str = "monokai"
    use_unicode: bool = True

    # Internal state
    content: str = ""
    is_complete: bool = False
    usage: Optional[Usage] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    def append(self, chunk: str) -> None:
        """Append a chunk to the streaming content.

        Args:
            chunk: Text chunk to append
        """
        self.content += chunk

    def complete(self, response: ModelResponse) -> None:
        """Mark the message as complete.

        Args:
            response: The complete model response
        """
        self.content = response.content
        self.is_complete = True
        self.usage = response.usage
        self.end_time = datetime.now()

    def get_duration(self) -> float:
        """Get the streaming duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def render(self) -> Panel:
        """Render the streaming message.

        Returns:
            Panel with current content and streaming cursor if not complete
        """
        # Add streaming cursor if not complete
        display_content = self.content
        if not self.is_complete:
            cursor = get_symbol("cursor", self.use_unicode)
            display_content += cursor

        # Render as markdown
        markdown = Markdown(display_content, code_theme=self.code_theme)

        # Build title
        title = Text()
        title.append(
            get_model_display_name(self.model),
            style=self.theme.get_model_style(self.model),
        )

        if self.is_complete and self.usage:
            title.append(f" ({self.usage.total_tokens} tokens)", style="dim")
            title.append(f" [{self.get_duration():.1f}s]", style="dim")
        elif not self.is_complete:
            title.append(" streaming...", style="dim italic")

        return Panel(
            markdown,
            title=title,
            title_align="left",
            border_style=self.theme.get_model_color(self.model),
            padding=(0, 1),
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


@dataclass
class DecisionIndicator:
    """Displays model speaking decisions."""

    model: str
    will_speak: bool
    confidence: float
    reason: str
    is_forced: bool
    theme: Theme
    use_unicode: bool = True

    def render(self) -> Text:
        """Render the decision indicator.

        Returns:
            Text showing the decision
        """
        text = Text()

        # Model name with color
        model_style = self.theme.get_model_style(self.model)
        text.append(get_model_display_name(self.model), style=model_style)
        text.append(": ")

        if self.will_speak:
            if self.is_forced:
                text.append("will speak ", style="green")
                text.append("(@mentioned)", style="dim")
            else:
                text.append("will speak ", style="green")
                text.append(f"(confidence: {self.confidence:.0%})", style="dim")
        else:
            text.append("staying silent ", style="dim")
            text.append(f"(confidence: {self.confidence:.0%})", style="dim")

        return text

    def __rich__(self) -> Text:
        """Rich protocol support."""
        return self.render()
