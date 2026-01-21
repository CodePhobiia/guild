"""Tool execution visualization components."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from codecrew.models.types import ToolCall, ToolResult
from codecrew.ui.theme import Theme, get_model_display_name, get_symbol


@dataclass
class ToolCallDisplay:
    """Display for a single tool call.

    Shows tool name, arguments, and status in a compact format.
    """

    tool_call: ToolCall
    model: str
    theme: Theme
    use_unicode: bool = True
    status: str = "pending"  # pending, executing, success, error
    result: Optional[ToolResult] = None
    execution_time: Optional[float] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    is_collapsed: bool = False

    def set_executing(self) -> None:
        """Mark as currently executing."""
        self.status = "executing"

    def set_complete(
        self,
        result: ToolResult,
        execution_time: Optional[float] = None,
    ) -> None:
        """Mark as complete with result.

        Args:
            result: Tool execution result
            execution_time: Execution time in seconds
        """
        self.result = result
        self.execution_time = execution_time
        self.end_time = datetime.now()
        self.status = "error" if result.is_error else "success"

    def toggle_collapsed(self) -> None:
        """Toggle collapsed state."""
        self.is_collapsed = not self.is_collapsed

    def _format_arguments(self) -> Text | Tree:
        """Format tool arguments for display.

        Returns:
            Formatted arguments
        """
        if not self.tool_call.arguments:
            return Text("(no arguments)", style="dim")

        if self.is_collapsed:
            # Show abbreviated version
            arg_count = len(self.tool_call.arguments)
            return Text(f"({arg_count} argument{'s' if arg_count != 1 else ''})", style="dim")

        # Show full arguments
        tree = Tree("Arguments")
        for key, value in self.tool_call.arguments.items():
            # Format value based on type
            if isinstance(value, str):
                if len(value) > 50:
                    display_value = f'"{value[:47]}..."'
                else:
                    display_value = f'"{value}"'
            elif isinstance(value, (list, dict)):
                display_value = f"[{type(value).__name__}]"
            else:
                display_value = str(value)

            tree.add(f"[cyan]{key}[/cyan]: {display_value}")

        return tree

    def _format_result(self) -> Text | Syntax | None:
        """Format tool result for display.

        Returns:
            Formatted result or None
        """
        if not self.result:
            return None

        content = self.result.content
        if isinstance(content, str):
            # Check if it looks like code/JSON
            if content.strip().startswith(("{", "[")):
                try:
                    return Syntax(content, "json", theme="monokai", line_numbers=False)
                except Exception:
                    pass

            # Truncate long content
            if len(content) > 200 and self.is_collapsed:
                content = content[:197] + "..."

            return Text(content)
        else:
            return Text(str(content))

    def render(self) -> Panel:
        """Render the tool call display.

        Returns:
            Panel containing the tool call visualization
        """
        # Header line
        header = Text()

        # Status symbol
        style = self.theme.get_tool_style(self.status)
        if self.status == "pending":
            symbol = "○"
        elif self.status == "executing":
            symbol = get_symbol("tool", self.use_unicode)
        elif self.status == "success":
            symbol = get_symbol("complete", self.use_unicode)
        else:  # error
            symbol = get_symbol("error", self.use_unicode)

        header.append(symbol, style=style)
        header.append(" ")

        # Tool name
        header.append(self.tool_call.name, style="bold yellow")

        # Execution time
        if self.execution_time is not None:
            header.append(f" ({self.execution_time:.2f}s)", style="dim")

        # Build content
        content_parts = []
        content_parts.append(header)

        # Arguments (if not collapsed or no result yet)
        if not self.is_collapsed or not self.result:
            args_display = self._format_arguments()
            content_parts.append(args_display)

        # Result
        if self.result:
            result_header = Text()
            if self.result.is_error:
                result_header.append("\nError: ", style="red bold")
            else:
                result_header.append("\nResult: ", style="green")
            content_parts.append(result_header)

            result_display = self._format_result()
            if result_display:
                content_parts.append(result_display)

        # Model attribution
        title = Text()
        model_style = self.theme.get_model_style(self.model)
        title.append(get_model_display_name(self.model), style=model_style)

        # Border color based on status
        if self.status == "error":
            border_style = "red"
        elif self.status == "success":
            border_style = "green"
        elif self.status == "executing":
            border_style = "yellow"
        else:
            border_style = "dim"

        return Panel(
            Group(*content_parts),
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


class ToolPanel:
    """Panel for displaying multiple tool calls and their results.

    Manages a collection of tool call displays and provides
    collapsible visualization.
    """

    def __init__(
        self,
        theme: Theme,
        use_unicode: bool = True,
        max_visible: int = 5,
        collapse_completed: bool = True,
    ):
        """Initialize the tool panel.

        Args:
            theme: Theme for styling
            use_unicode: Whether to use Unicode characters
            max_visible: Maximum visible tool calls before scrolling
            collapse_completed: Auto-collapse completed tool calls
        """
        self.theme = theme
        self.use_unicode = use_unicode
        self.max_visible = max_visible
        self.collapse_completed = collapse_completed
        self._calls: list[ToolCallDisplay] = []

    def add_call(self, tool_call: ToolCall, model: str) -> ToolCallDisplay:
        """Add a new tool call.

        Args:
            tool_call: The tool call
            model: Model that made the call

        Returns:
            ToolCallDisplay instance
        """
        display = ToolCallDisplay(
            tool_call=tool_call,
            model=model,
            theme=self.theme,
            use_unicode=self.use_unicode,
        )
        self._calls.append(display)
        return display

    def update_call(
        self,
        tool_call_id: str,
        result: ToolResult,
        execution_time: Optional[float] = None,
    ) -> Optional[ToolCallDisplay]:
        """Update a tool call with its result.

        Args:
            tool_call_id: ID of the tool call
            result: Execution result
            execution_time: Execution time in seconds

        Returns:
            Updated ToolCallDisplay or None if not found
        """
        for display in self._calls:
            if display.tool_call.id == tool_call_id:
                display.set_complete(result, execution_time)
                if self.collapse_completed:
                    display.is_collapsed = True
                return display
        return None

    def get_call(self, tool_call_id: str) -> Optional[ToolCallDisplay]:
        """Get a tool call display by ID.

        Args:
            tool_call_id: ID of the tool call

        Returns:
            ToolCallDisplay or None
        """
        for display in self._calls:
            if display.tool_call.id == tool_call_id:
                return display
        return None

    def clear(self) -> None:
        """Clear all tool calls."""
        self._calls.clear()

    @property
    def call_count(self) -> int:
        """Get the number of tool calls."""
        return len(self._calls)

    @property
    def pending_count(self) -> int:
        """Get the number of pending tool calls."""
        return sum(1 for c in self._calls if c.status in ("pending", "executing"))

    def render(self) -> Group | Text:
        """Render all tool calls.

        Returns:
            Group of tool call panels or empty text
        """
        if not self._calls:
            return Text()

        # Determine which calls to show
        visible_calls = self._calls[-self.max_visible :]
        hidden_count = len(self._calls) - len(visible_calls)

        panels = []

        # Show hidden count indicator
        if hidden_count > 0:
            hidden_text = Text(
                f"... {hidden_count} earlier tool call{'s' if hidden_count > 1 else ''} ...",
                style="dim",
            )
            panels.append(hidden_text)

        # Render visible calls
        for display in visible_calls:
            panels.append(display.render())

        return Group(*panels)

    def render_summary(self) -> Text:
        """Render a summary line of tool calls.

        Returns:
            Text with summary information
        """
        text = Text()

        if not self._calls:
            return text

        total = len(self._calls)
        success = sum(1 for c in self._calls if c.status == "success")
        errors = sum(1 for c in self._calls if c.status == "error")
        pending = sum(1 for c in self._calls if c.status in ("pending", "executing"))

        text.append(f"Tools: {total} ", style="dim")
        if success:
            text.append(f"{success} ok ", style="green")
        if errors:
            text.append(f"{errors} err ", style="red")
        if pending:
            text.append(f"{pending} pending", style="yellow")

        return text

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


@dataclass
class PermissionRequestDisplay:
    """Display for a tool permission request."""

    tool_name: str
    tool_call: ToolCall
    permission_level: str  # safe, cautious, dangerous
    model: str
    theme: Theme
    use_unicode: bool = True
    reason: Optional[str] = None

    def render(self) -> Panel:
        """Render the permission request.

        Returns:
            Panel with permission request details
        """
        content = Text()

        # Warning icon
        content.append(get_symbol("warning", self.use_unicode), style="yellow bold")
        content.append(" ")

        # Title
        content.append("Permission Required\n\n", style="bold")

        # Tool info
        content.append("Tool: ", style="dim")
        content.append(self.tool_name, style="bold yellow")
        content.append("\n")

        # Permission level
        content.append("Level: ", style="dim")
        if self.permission_level == "dangerous":
            content.append("DANGEROUS", style="red bold")
        elif self.permission_level == "cautious":
            content.append("CAUTIOUS", style="yellow")
        else:
            content.append(self.permission_level.upper(), style="green")
        content.append("\n")

        # Arguments
        if self.tool_call.arguments:
            content.append("\nArguments:\n", style="dim")
            for key, value in self.tool_call.arguments.items():
                content.append(f"  {key}: ", style="cyan")
                str_value = str(value)
                if len(str_value) > 60:
                    str_value = str_value[:57] + "..."
                content.append(f"{str_value}\n")

        # Reason
        if self.reason:
            content.append(f"\nReason: {self.reason}\n", style="dim")

        # Options
        content.append("\n[Y]es  [N]o  [A]lways  [Never]", style="bright_cyan")

        # Model attribution
        title = Text()
        model_style = self.theme.get_model_style(self.model)
        title.append(get_model_display_name(self.model), style=model_style)
        title.append(" requests permission")

        return Panel(
            content,
            title=title,
            title_align="left",
            border_style="yellow",
            padding=(1, 2),
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()
