"""CodeCrew TUI - Rich Terminal User Interface.

This package provides the interactive terminal interface for CodeCrew,
including real-time message streaming, tool visualization, and session management.
"""

from codecrew.ui.app import ChatApp, create_chat_app
from codecrew.ui.clipboard import ClipboardManager, clipboard_available, copy_to_clipboard, paste_from_clipboard
from codecrew.ui.history import HistoryEntry, HistoryManager, PersistentHistory
from codecrew.ui.keybindings import DEFAULT_BINDINGS, KeyBinding, KeyBindingManager
from codecrew.ui.navigation import NavigationManager, NavigationState, SearchResult
from codecrew.ui.theme import (
    THEMES,
    Theme,
    ThemeName,
    get_model_display_name,
    get_symbol,
    get_theme,
    list_themes,
)

__all__ = [
    # Main app
    "ChatApp",
    "create_chat_app",
    # Theme system
    "Theme",
    "ThemeName",
    "THEMES",
    "get_theme",
    "list_themes",
    "get_model_display_name",
    "get_symbol",
    # History
    "HistoryManager",
    "HistoryEntry",
    "PersistentHistory",
    # Keybindings
    "KeyBindingManager",
    "KeyBinding",
    "DEFAULT_BINDINGS",
    # Navigation
    "NavigationManager",
    "NavigationState",
    "SearchResult",
    # Clipboard
    "ClipboardManager",
    "copy_to_clipboard",
    "paste_from_clipboard",
    "clipboard_available",
]
