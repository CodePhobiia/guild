"""Theme definitions and color schemes for the TUI."""

from dataclasses import dataclass, field
from typing import Literal

from rich.style import Style


@dataclass
class Theme:
    """Color scheme and styling definitions for the TUI."""

    name: str
    description: str

    # Model colors for badges and borders
    model_colors: dict[str, str] = field(default_factory=dict)

    # Styles for different message roles
    message_styles: dict[str, Style] = field(default_factory=dict)

    # UI element styles
    ui_styles: dict[str, Style] = field(default_factory=dict)

    # Tool-related styles
    tool_styles: dict[str, Style] = field(default_factory=dict)

    # Status indicators
    status_styles: dict[str, Style] = field(default_factory=dict)

    def get_model_color(self, model: str) -> str:
        """Get the color for a model, with fallback."""
        return self.model_colors.get(model.lower(), "white")

    def get_model_style(self, model: str) -> Style:
        """Get a Style object for a model."""
        color = self.get_model_color(model)
        return Style(color=color)

    def get_message_style(self, role: str) -> Style:
        """Get the style for a message role."""
        return self.message_styles.get(role.lower(), Style())

    def get_ui_style(self, element: str) -> Style:
        """Get the style for a UI element."""
        return self.ui_styles.get(element, Style())

    def get_tool_style(self, status: str) -> Style:
        """Get the style for a tool status."""
        return self.tool_styles.get(status, Style())

    def get_status_style(self, status: str) -> Style:
        """Get the style for a status indicator."""
        return self.status_styles.get(status, Style())


# Default theme - vibrant colors for each model
DEFAULT_THEME = Theme(
    name="default",
    description="Vibrant colors with distinct model identities",
    model_colors={
        "claude": "orange3",
        "gpt": "green",
        "gemini": "blue",
        "grok": "purple",
        "user": "bright_white",
        "system": "grey50",
        "tool": "yellow",
    },
    message_styles={
        "user": Style(color="bright_white", bold=True),
        "assistant": Style(color="white"),
        "system": Style(color="grey50", dim=True, italic=True),
        "error": Style(color="red", bold=True),
        "tool": Style(color="yellow"),
    },
    ui_styles={
        "header": Style(bgcolor="grey15"),
        "header_text": Style(color="bright_white", bold=True),
        "status_bar": Style(bgcolor="grey19"),
        "status_text": Style(color="bright_white"),
        "border": Style(color="grey50"),
        "border_focused": Style(color="bright_blue"),
        "input_prompt": Style(color="bright_cyan", bold=True),
        "input_text": Style(color="white"),
        "hint": Style(color="grey58", italic=True),
        "separator": Style(color="grey35"),
    },
    tool_styles={
        "pending": Style(color="yellow"),
        "executing": Style(color="bright_yellow", bold=True),
        "success": Style(color="green"),
        "error": Style(color="red"),
        "permission": Style(color="bright_magenta", bold=True),
    },
    status_styles={
        "thinking": Style(color="bright_yellow"),
        "streaming": Style(color="bright_green"),
        "idle": Style(color="grey50"),
        "error": Style(color="bright_red"),
        "saved": Style(color="green"),
        "warning": Style(color="yellow"),
    },
)


# Minimal theme - reduced colors for distraction-free work
MINIMAL_THEME = Theme(
    name="minimal",
    description="Reduced colors for distraction-free work",
    model_colors={
        "claude": "bright_white",
        "gpt": "bright_white",
        "gemini": "bright_white",
        "grok": "bright_white",
        "user": "white",
        "system": "grey50",
        "tool": "white",
    },
    message_styles={
        "user": Style(color="white", bold=True),
        "assistant": Style(color="bright_white"),
        "system": Style(color="grey50", dim=True),
        "error": Style(color="red"),
        "tool": Style(color="white"),
    },
    ui_styles={
        "header": Style(bgcolor="grey11"),
        "header_text": Style(color="white"),
        "status_bar": Style(bgcolor="grey11"),
        "status_text": Style(color="white"),
        "border": Style(color="grey35"),
        "border_focused": Style(color="white"),
        "input_prompt": Style(color="white", bold=True),
        "input_text": Style(color="white"),
        "hint": Style(color="grey50"),
        "separator": Style(color="grey23"),
    },
    tool_styles={
        "pending": Style(color="white"),
        "executing": Style(color="white", bold=True),
        "success": Style(color="white"),
        "error": Style(color="red"),
        "permission": Style(color="white", bold=True),
    },
    status_styles={
        "thinking": Style(color="white"),
        "streaming": Style(color="white"),
        "idle": Style(color="grey50"),
        "error": Style(color="red"),
        "saved": Style(color="white"),
        "warning": Style(color="white"),
    },
)


# Colorblind-friendly theme - uses patterns and high-contrast colors
COLORBLIND_THEME = Theme(
    name="colorblind",
    description="High-contrast colors optimized for color vision deficiency",
    model_colors={
        # Using colors that are distinguishable for most color vision deficiencies
        "claude": "bright_yellow",  # Yellow is generally safe
        "gpt": "bright_cyan",  # Cyan/blue is safe
        "gemini": "bright_magenta",  # Magenta works for most
        "grok": "bright_white",  # White is always visible
        "user": "white",
        "system": "grey70",
        "tool": "bright_yellow",
    },
    message_styles={
        "user": Style(color="white", bold=True),
        "assistant": Style(color="bright_white"),
        "system": Style(color="grey70", dim=True),
        "error": Style(color="bright_red", bold=True, underline=True),
        "tool": Style(color="bright_yellow"),
    },
    ui_styles={
        "header": Style(bgcolor="grey15"),
        "header_text": Style(color="bright_white", bold=True),
        "status_bar": Style(bgcolor="grey19"),
        "status_text": Style(color="bright_white"),
        "border": Style(color="grey62"),
        "border_focused": Style(color="bright_white"),
        "input_prompt": Style(color="bright_cyan", bold=True),
        "input_text": Style(color="white"),
        "hint": Style(color="grey70"),
        "separator": Style(color="grey50"),
    },
    tool_styles={
        "pending": Style(color="bright_yellow"),
        "executing": Style(color="bright_yellow", bold=True, blink=True),
        "success": Style(color="bright_cyan"),
        "error": Style(color="bright_red", underline=True),
        "permission": Style(color="bright_magenta", bold=True),
    },
    status_styles={
        "thinking": Style(color="bright_yellow", bold=True),
        "streaming": Style(color="bright_cyan"),
        "idle": Style(color="grey62"),
        "error": Style(color="bright_red", bold=True),
        "saved": Style(color="bright_cyan"),
        "warning": Style(color="bright_yellow"),
    },
)


# Theme registry
THEMES: dict[str, Theme] = {
    "default": DEFAULT_THEME,
    "minimal": MINIMAL_THEME,
    "colorblind": COLORBLIND_THEME,
}

ThemeName = Literal["default", "minimal", "colorblind"]


def get_theme(name: ThemeName) -> Theme:
    """Get a theme by name.

    Args:
        name: Theme name (default, minimal, or colorblind)

    Returns:
        The requested Theme instance

    Raises:
        KeyError: If theme name is not found
    """
    if name not in THEMES:
        raise KeyError(f"Unknown theme: {name}. Available: {list(THEMES.keys())}")
    return THEMES[name]


def list_themes() -> list[str]:
    """Get list of available theme names."""
    return list(THEMES.keys())


# Model name mappings for display
MODEL_DISPLAY_NAMES: dict[str, str] = {
    "claude": "Claude",
    "gpt": "GPT",
    "gemini": "Gemini",
    "grok": "Grok",
}


def get_model_display_name(model: str) -> str:
    """Get the display name for a model."""
    return MODEL_DISPLAY_NAMES.get(model.lower(), model.capitalize())


# Unicode symbols for status indicators
SYMBOLS = {
    "thinking": "\u2026",  # Horizontal ellipsis ...
    "streaming": "\u25b6",  # Play triangle
    "complete": "\u2713",  # Check mark
    "error": "\u2717",  # X mark
    "warning": "\u26a0",  # Warning triangle
    "pin": "\U0001F4CC",  # Pushpin emoji (with fallback)
    "tool": "\u2699",  # Gear
    "user": "\u276f",  # Heavy right-pointing angle bracket
    "assistant": "\u25cf",  # Black circle
    "cursor": "\u2588",  # Full block (for streaming cursor)
}


# Fallback ASCII symbols for terminals without Unicode support
ASCII_SYMBOLS = {
    "thinking": "...",
    "streaming": ">",
    "complete": "[OK]",
    "error": "[X]",
    "warning": "[!]",
    "pin": "[*]",
    "tool": "[T]",
    "user": ">",
    "assistant": "*",
    "cursor": "_",
}


def get_symbol(name: str, use_unicode: bool = True) -> str:
    """Get a symbol by name.

    Args:
        name: Symbol name
        use_unicode: Whether to use Unicode symbols (default True)

    Returns:
        The symbol string
    """
    symbols = SYMBOLS if use_unicode else ASCII_SYMBOLS
    return symbols.get(name, "")
