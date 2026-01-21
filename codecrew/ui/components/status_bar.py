"""Status bar component for the TUI."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codecrew.models.types import Usage
from codecrew.ui.theme import Theme, get_model_display_name, get_symbol


@dataclass
class StatusBar:
    """Status bar component showing token usage, cost, and status.

    Displays:
    - Token usage (current/max)
    - Estimated cost
    - Active model indicator
    - Last save time
    - Current status (idle, thinking, streaming, error)
    """

    theme: Theme
    use_unicode: bool = True

    # Token tracking
    total_tokens: int = 0
    max_tokens: int = 100000

    # Cost tracking
    total_cost: float = 0.0
    show_cost: bool = True

    # Status
    status: str = "idle"  # idle, thinking, streaming, error
    status_message: Optional[str] = None
    active_model: Optional[str] = None

    # Save info
    last_saved: Optional[datetime] = None
    is_modified: bool = False

    def update_usage(self, usage: Usage) -> None:
        """Update token usage from a Usage object.

        Args:
            usage: Usage object with token counts
        """
        if usage.total_tokens:
            self.total_tokens += usage.total_tokens

    def add_tokens(self, tokens: int) -> None:
        """Add tokens to the total count.

        Args:
            tokens: Number of tokens to add
        """
        self.total_tokens += tokens

    def add_cost(self, cost: float) -> None:
        """Add to the total cost.

        Args:
            cost: Cost to add
        """
        self.total_cost += cost

    def set_status(
        self,
        status: str,
        message: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Set the current status.

        Args:
            status: Status string (idle, thinking, streaming, error)
            message: Optional status message
            model: Optional active model name
        """
        self.status = status
        self.status_message = message
        self.active_model = model

    def mark_saved(self) -> None:
        """Mark that the session was just saved."""
        self.last_saved = datetime.now()
        self.is_modified = False

    def mark_modified(self) -> None:
        """Mark that the session has unsaved changes."""
        self.is_modified = True

    def reset(self) -> None:
        """Reset all tracking values."""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.status = "idle"
        self.status_message = None
        self.active_model = None
        self.last_saved = None
        self.is_modified = False

    def _format_tokens(self) -> Text:
        """Format token count display.

        Returns:
            Formatted token text
        """
        text = Text()

        # Calculate percentage
        percentage = (self.total_tokens / self.max_tokens * 100) if self.max_tokens else 0

        # Color based on usage
        if percentage > 90:
            color = "red"
        elif percentage > 70:
            color = "yellow"
        else:
            color = "green"

        text.append("Tokens: ", style="dim")
        text.append(f"{self.total_tokens:,}", style=color)
        text.append(f"/{self.max_tokens:,}", style="dim")

        return text

    def _format_cost(self) -> Text:
        """Format cost display.

        Returns:
            Formatted cost text
        """
        text = Text()
        text.append("Cost: ", style="dim")
        text.append(f"${self.total_cost:.4f}", style="cyan")
        return text

    def _format_status(self) -> Text:
        """Format status display.

        Returns:
            Formatted status text
        """
        text = Text()

        style = self.theme.get_status_style(self.status)
        symbol = get_symbol(self.status, self.use_unicode)

        if symbol:
            text.append(symbol, style=style)
            text.append(" ")

        if self.status == "thinking":
            text.append("Thinking...", style=style)
        elif self.status == "streaming":
            if self.active_model:
                model_style = self.theme.get_model_style(self.active_model)
                text.append(get_model_display_name(self.active_model), style=model_style)
                text.append(" responding...", style=style)
            else:
                text.append("Streaming...", style=style)
        elif self.status == "error":
            text.append("Error", style=style)
            if self.status_message:
                text.append(f": {self.status_message}", style="dim")
        else:  # idle
            text.append("Ready", style=style)

        return text

    def _format_save_status(self) -> Text:
        """Format save status display.

        Returns:
            Formatted save status text
        """
        text = Text()

        if self.is_modified:
            text.append(get_symbol("warning", self.use_unicode), style="yellow")
            text.append(" ", style="dim")
            text.append("Modified", style="yellow")
        elif self.last_saved:
            text.append(get_symbol("complete", self.use_unicode), style="green")
            text.append(" ", style="dim")
            text.append(f"Saved {self.last_saved.strftime('%H:%M')}", style="dim")

        return text

    def render(self) -> Panel:
        """Render the status bar.

        Returns:
            Panel containing the status bar
        """
        # Create a table for layout
        table = Table.grid(expand=True)
        table.add_column("tokens", justify="left", ratio=1)
        table.add_column("cost", justify="left", ratio=1)
        table.add_column("status", justify="center", ratio=2)
        table.add_column("save", justify="right", ratio=1)

        table.add_row(
            self._format_tokens(),
            self._format_cost() if self.show_cost else Text(),
            self._format_status(),
            self._format_save_status(),
        )

        return Panel(
            table,
            style=self.theme.get_ui_style("status_bar"),
            border_style=self.theme.get_ui_style("border"),
            padding=(0, 1),
        )

    def render_compact(self) -> Text:
        """Render a compact single-line status bar.

        Returns:
            Text containing the compact status
        """
        text = Text()

        # Tokens
        text.append_text(self._format_tokens())
        text.append(" | ", style="dim")

        # Cost
        if self.show_cost:
            text.append_text(self._format_cost())
            text.append(" | ", style="dim")

        # Status
        text.append_text(self._format_status())

        # Save indicator
        if self.is_modified:
            text.append(" | ", style="dim")
            text.append("*", style="yellow")

        return text

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


@dataclass
class MiniStatus:
    """Minimal status indicator for inline display."""

    theme: Theme
    use_unicode: bool = True
    status: str = "idle"
    model: Optional[str] = None

    def render(self) -> Text:
        """Render the mini status.

        Returns:
            Text containing the status indicator
        """
        text = Text()

        style = self.theme.get_status_style(self.status)
        symbol = get_symbol(self.status, self.use_unicode)

        if symbol:
            text.append(symbol, style=style)

        if self.model:
            text.append(" ")
            model_style = self.theme.get_model_style(self.model)
            text.append(get_model_display_name(self.model), style=model_style)

        return text

    def __rich__(self) -> Text:
        """Rich protocol support."""
        return self.render()
