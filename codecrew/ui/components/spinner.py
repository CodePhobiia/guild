"""Spinner and loading indicator components."""

import time
from enum import Enum
from typing import Optional

from rich.console import RenderableType
from rich.text import Text

from codecrew.ui.theme import Theme, get_model_display_name


class SpinnerType(Enum):
    """Types of spinners for different operations."""

    THINKING = "thinking"
    EVALUATING = "evaluating"
    GENERATING = "generating"
    EXECUTING = "executing"


# Spinner animation frames
SPINNER_FRAMES = {
    SpinnerType.THINKING: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    SpinnerType.EVALUATING: ["◐", "◓", "◑", "◒"],
    SpinnerType.GENERATING: ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"],
    SpinnerType.EXECUTING: ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
}

# ASCII fallback frames
ASCII_SPINNER_FRAMES = {
    SpinnerType.THINKING: ["|", "/", "-", "\\"],
    SpinnerType.EVALUATING: [".", "o", "O", "o"],
    SpinnerType.GENERATING: ["[  ]", "[= ]", "[==]", "[ =]"],
    SpinnerType.EXECUTING: ["-", "\\", "|", "/"],
}


class Spinner:
    """Animated spinner for loading states.

    Provides various spinner animations for different operations
    like thinking, evaluating models, generating responses, and
    executing tools.
    """

    def __init__(
        self,
        spinner_type: SpinnerType = SpinnerType.THINKING,
        theme: Optional[Theme] = None,
        use_unicode: bool = True,
        speed: float = 0.1,
    ):
        """Initialize the spinner.

        Args:
            spinner_type: Type of spinner animation
            theme: Theme for styling
            use_unicode: Whether to use Unicode characters
            speed: Animation speed in seconds per frame
        """
        self.spinner_type = spinner_type
        self.theme = theme
        self.use_unicode = use_unicode
        self.speed = speed
        self._start_time = time.time()
        self._message: Optional[str] = None
        self._model: Optional[str] = None

    @property
    def frames(self) -> list[str]:
        """Get the animation frames for current spinner type."""
        if self.use_unicode:
            return SPINNER_FRAMES[self.spinner_type]
        return ASCII_SPINNER_FRAMES[self.spinner_type]

    @property
    def current_frame(self) -> str:
        """Get the current animation frame based on elapsed time."""
        elapsed = time.time() - self._start_time
        frame_index = int(elapsed / self.speed) % len(self.frames)
        return self.frames[frame_index]

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds since spinner started."""
        return time.time() - self._start_time

    def format_elapsed(self) -> str:
        """Format elapsed time as a human-readable string.

        Returns:
            Formatted time string like '5s', '1m 23s', '2m 5s'
        """
        elapsed = self.elapsed_seconds
        if elapsed < 60:
            return f"{int(elapsed)}s"
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"

    def set_message(self, message: str) -> None:
        """Set the message to display alongside the spinner."""
        self._message = message

    def set_model(self, model: str) -> None:
        """Set the model name for styled display."""
        self._model = model

    def reset(self) -> None:
        """Reset the spinner animation."""
        self._start_time = time.time()

    def render(self) -> RenderableType:
        """Render the spinner as Rich text.

        Returns:
            Rich Text object with the spinner and message
        """
        text = Text()

        # Get style based on spinner type
        if self.theme:
            if self.spinner_type == SpinnerType.THINKING:
                style = self.theme.get_status_style("thinking")
            elif self.spinner_type == SpinnerType.EXECUTING:
                style = self.theme.get_tool_style("executing")
            else:
                style = self.theme.get_status_style("streaming")
        else:
            style = None

        # Add spinner frame
        text.append(self.current_frame, style=style)
        text.append(" ")

        # Add model name if set
        if self._model and self.theme:
            model_style = self.theme.get_model_style(self._model)
            text.append(get_model_display_name(self._model), style=model_style)
            text.append(" ")

        # Add message
        if self._message:
            text.append(self._message, style=style)

        return text

    def __rich__(self) -> RenderableType:
        """Rich protocol support."""
        return self.render()


class ThinkingIndicator:
    """Indicator shown when models are being evaluated."""

    def __init__(
        self,
        models: list[str],
        theme: Optional[Theme] = None,
        use_unicode: bool = True,
    ):
        """Initialize the thinking indicator.

        Args:
            models: List of model names being evaluated
            theme: Theme for styling
            use_unicode: Whether to use Unicode characters
        """
        self.models = models
        self.theme = theme
        self.spinner = Spinner(
            spinner_type=SpinnerType.THINKING,
            theme=theme,
            use_unicode=use_unicode,
        )

    def render(self) -> RenderableType:
        """Render the thinking indicator."""
        text = Text()

        # Spinner
        text.append(self.spinner.current_frame)
        text.append(" ")

        # Message
        text.append("Thinking", style="bold")
        text.append(" ")

        # Model names
        if self.theme:
            for i, model in enumerate(self.models):
                if i > 0:
                    text.append(", ")
                style = self.theme.get_model_style(model)
                text.append(get_model_display_name(model), style=style)
        else:
            text.append(", ".join(get_model_display_name(m) for m in self.models))

        text.append("... ")

        # Elapsed time
        text.append(f"[{self.spinner.format_elapsed()}]", style="dim")

        return text

    def __rich__(self) -> RenderableType:
        """Rich protocol support."""
        return self.render()


class TypingIndicator:
    """Indicator shown when a model is generating a response."""

    def __init__(
        self,
        model: str,
        theme: Optional[Theme] = None,
        use_unicode: bool = True,
    ):
        """Initialize the typing indicator.

        Args:
            model: Model name
            theme: Theme for styling
            use_unicode: Whether to use Unicode characters
        """
        self.model = model
        self.theme = theme
        self.spinner = Spinner(
            spinner_type=SpinnerType.GENERATING,
            theme=theme,
            use_unicode=use_unicode,
        )

    def render(self) -> RenderableType:
        """Render the typing indicator."""
        text = Text()

        # Spinner
        text.append(self.spinner.current_frame)
        text.append(" ")

        # Model name
        if self.theme:
            style = self.theme.get_model_style(self.model)
            text.append(get_model_display_name(self.model), style=style)
        else:
            text.append(get_model_display_name(self.model))

        text.append(" is typing... ")

        # Elapsed time
        text.append(f"[{self.spinner.format_elapsed()}]", style="dim")

        return text

    def __rich__(self) -> RenderableType:
        """Rich protocol support."""
        return self.render()


class ToolExecutingIndicator:
    """Indicator shown when a tool is being executed."""

    def __init__(
        self,
        tool_name: str,
        model: str,
        theme: Optional[Theme] = None,
        use_unicode: bool = True,
    ):
        """Initialize the tool executing indicator.

        Args:
            tool_name: Name of the tool being executed
            model: Model that requested the tool
            theme: Theme for styling
            use_unicode: Whether to use Unicode characters
        """
        self.tool_name = tool_name
        self.model = model
        self.theme = theme
        self.spinner = Spinner(
            spinner_type=SpinnerType.EXECUTING,
            theme=theme,
            use_unicode=use_unicode,
        )

    def render(self) -> RenderableType:
        """Render the tool executing indicator."""
        text = Text()

        # Spinner
        text.append(self.spinner.current_frame)
        text.append(" ")

        # Tool icon
        text.append("\u2699 ", style="yellow" if not self.theme else None)

        # Message
        if self.theme:
            style = self.theme.get_model_style(self.model)
            text.append(get_model_display_name(self.model), style=style)
        else:
            text.append(get_model_display_name(self.model))

        text.append(" executing ")
        text.append(self.tool_name, style="bold yellow")
        text.append("... ")

        # Elapsed time
        text.append(f"[{self.spinner.format_elapsed()}]", style="dim")

        return text

    def __rich__(self) -> RenderableType:
        """Rich protocol support."""
        return self.render()
