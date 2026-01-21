"""Header component for the TUI."""

from dataclasses import dataclass
from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codecrew.ui.theme import Theme, get_model_display_name


@dataclass
class Header:
    """Header bar component showing session and model information.

    Displays:
    - Session name and ID
    - Available models with colored indicators
    - Current project path
    """

    theme: Theme
    session_name: Optional[str] = None
    session_id: Optional[str] = None
    project_path: Optional[str] = None
    available_models: list[str] | None = None
    version: str = ""

    def set_session(
        self,
        name: Optional[str] = None,
        session_id: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> None:
        """Update session information.

        Args:
            name: Session name
            session_id: Session ID
            project_path: Project path
        """
        self.session_name = name
        self.session_id = session_id
        self.project_path = project_path

    def set_models(self, models: list[str]) -> None:
        """Set available models.

        Args:
            models: List of available model names
        """
        self.available_models = models

    def render(self) -> Panel:
        """Render the header.

        Returns:
            Panel containing the header content
        """
        # Create a table for layout
        table = Table.grid(expand=True)
        table.add_column("left", justify="left", ratio=1)
        table.add_column("center", justify="center", ratio=2)
        table.add_column("right", justify="right", ratio=1)

        # Left: Session info
        left_text = Text()
        if self.session_name:
            left_text.append(self.session_name, style="bold")
        elif self.session_id:
            left_text.append(f"Session: {self.session_id[:8]}...", style="dim")
        else:
            left_text.append("New Session", style="dim italic")

        # Center: Models
        center_text = Text()
        if self.available_models:
            for i, model in enumerate(self.available_models):
                if i > 0:
                    center_text.append(" | ", style="dim")
                color = self.theme.get_model_color(model)
                center_text.append(get_model_display_name(model), style=color)
        else:
            center_text.append("No models available", style="dim")

        # Right: Version and project
        right_text = Text()
        if self.project_path:
            # Truncate long paths
            path = self.project_path
            if len(path) > 30:
                path = "..." + path[-27:]
            right_text.append(path, style="dim")
        if self.version:
            if self.project_path:
                right_text.append(" | ", style="dim")
            right_text.append(f"v{self.version}", style="dim")

        table.add_row(left_text, center_text, right_text)

        return Panel(
            table,
            style=self.theme.get_ui_style("header"),
            border_style=self.theme.get_ui_style("border"),
            padding=(0, 1),
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


class CompactHeader:
    """Compact single-line header for minimal display."""

    def __init__(
        self,
        theme: Theme,
        session_name: Optional[str] = None,
        available_models: Optional[list[str]] = None,
    ):
        """Initialize compact header.

        Args:
            theme: Theme for styling
            session_name: Current session name
            available_models: List of available models
        """
        self.theme = theme
        self.session_name = session_name
        self.available_models = available_models or []

    def render(self) -> Text:
        """Render the compact header.

        Returns:
            Text containing the header line
        """
        text = Text()

        # Session
        text.append("CodeCrew", style="bold bright_white")
        if self.session_name:
            text.append(f" [{self.session_name}]", style="dim")

        text.append(" - ", style="dim")

        # Models
        for i, model in enumerate(self.available_models):
            if i > 0:
                text.append(" ", style="dim")
            color = self.theme.get_model_color(model)
            # Use first letter as badge
            text.append(f"[{model[0].upper()}]", style=color)

        return text

    def __rich__(self) -> Text:
        """Rich protocol support."""
        return self.render()
