"""Keyboard binding system for the TUI."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import aiosqlite
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

logger = logging.getLogger(__name__)


@dataclass
class KeyBinding:
    """A single keyboard binding."""

    key: str  # e.g., "c-l", "c-r", "f1", "pageup"
    action: str  # e.g., "clear_screen", "search_history"
    description: str
    category: str  # "navigation", "editing", "display", "session"

    @property
    def display_key(self) -> str:
        """Get a human-readable key name."""
        key_names = {
            "c-": "Ctrl+",
            "s-": "Shift+",
            "escape": "Esc",
            "pageup": "Page Up",
            "pagedown": "Page Down",
        }
        result = self.key
        for prefix, display in key_names.items():
            if result.startswith(prefix):
                result = display + result[len(prefix):].upper()
                break
            elif result == prefix.rstrip("-"):
                result = display.rstrip("+")
                break
        return result


# Default key bindings
DEFAULT_BINDINGS: dict[str, tuple[str, str, str]] = {
    # Format: key -> (action, description, category)
    # Display/Screen
    "c-l": ("clear_screen", "Clear the screen", "display"),
    "f5": ("refresh", "Refresh display", "display"),
    "f3": ("toggle_compact", "Toggle compact mode", "display"),
    "f4": ("toggle_decisions", "Toggle decision visibility", "display"),
    # History
    "c-r": ("search_history", "Search input history", "editing"),
    "c-p": ("previous_history", "Previous history entry", "editing"),
    "c-n": ("next_history", "Next history entry", "editing"),
    # Editing
    "c-u": ("clear_line", "Clear current line", "editing"),
    "c-w": ("delete_word", "Delete previous word", "editing"),
    "c-k": ("kill_line", "Delete to end of line", "editing"),
    "c-a": ("beginning_of_line", "Move to beginning of line", "editing"),
    "c-e": ("end_of_line", "Move to end of line", "editing"),
    # Navigation
    "pageup": ("scroll_up", "Scroll messages up", "navigation"),
    "pagedown": ("scroll_down", "Scroll messages down", "navigation"),
    "home": ("scroll_top", "Scroll to top", "navigation"),
    "end": ("scroll_bottom", "Scroll to bottom", "navigation"),
    "c-f": ("search_messages", "Search messages", "navigation"),
    # Help
    "f1": ("show_help", "Show help", "display"),
    "f2": ("show_commands", "Show all commands", "display"),
    # Session
    "c-s": ("save_session", "Save current session", "session"),
    "c-o": ("open_session", "Open session picker", "session"),
}


class KeyBindingManager:
    """Manages keyboard shortcuts with customization support.

    Handles loading/saving custom bindings from the database
    and creating prompt_toolkit compatible key bindings.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the key binding manager.

        Args:
            db_path: Path to database for custom bindings (None for defaults only)
        """
        self.db_path = db_path
        self._bindings: dict[str, KeyBinding] = {}
        self._action_handlers: dict[str, Callable] = {}

        # Load default bindings
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load the default key bindings."""
        for key, (action, description, category) in DEFAULT_BINDINGS.items():
            self._bindings[key] = KeyBinding(
                key=key,
                action=action,
                description=description,
                category=category,
            )

    async def load_custom_bindings(self) -> None:
        """Load custom bindings from the database."""
        if not self.db_path:
            return

        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute(
                    "SELECT key, action FROM key_bindings"
                )
                rows = await cursor.fetchall()

                for key, action in rows:
                    if key in self._bindings:
                        # Update existing binding's action
                        self._bindings[key] = KeyBinding(
                            key=key,
                            action=action,
                            description=self._bindings[key].description,
                            category=self._bindings[key].category,
                        )
        except (OSError, aiosqlite.Error) as e:
            # Table might not exist yet or database unavailable, that's okay
            logger.debug(f"Could not load custom key bindings: {e}")

    async def save_binding(self, key: str, action: str) -> None:
        """Save a custom binding to the database.

        Args:
            key: The key combination
            action: The action to perform
        """
        if not self.db_path:
            return

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO key_bindings (key, action, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, action, datetime.now(timezone.utc).isoformat()),
            )
            await conn.commit()

    async def remove_binding(self, key: str) -> bool:
        """Remove a custom binding.

        Args:
            key: The key to unbind

        Returns:
            True if removed, False if not found
        """
        if key not in self._bindings:
            return False

        # Reset to default if exists, otherwise remove
        if key in DEFAULT_BINDINGS:
            action, description, category = DEFAULT_BINDINGS[key]
            self._bindings[key] = KeyBinding(
                key=key,
                action=action,
                description=description,
                category=category,
            )
        else:
            del self._bindings[key]

        # Remove from database
        if self.db_path:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    "DELETE FROM key_bindings WHERE key = ?",
                    (key,),
                )
                await conn.commit()

        return True

    def get_binding(self, key: str) -> Optional[KeyBinding]:
        """Get a binding by key.

        Args:
            key: The key combination

        Returns:
            The KeyBinding or None
        """
        return self._bindings.get(key)

    def get_action(self, key: str) -> Optional[str]:
        """Get the action for a key.

        Args:
            key: The key combination

        Returns:
            The action name or None
        """
        binding = self._bindings.get(key)
        return binding.action if binding else None

    def set_binding(self, key: str, action: str, description: str = "", category: str = "custom") -> None:
        """Set a binding (in memory).

        Args:
            key: The key combination
            action: The action to perform
            description: Description of the binding
            category: Category for grouping
        """
        self._bindings[key] = KeyBinding(
            key=key,
            action=action,
            description=description or f"Custom: {action}",
            category=category,
        )

    def get_all_bindings(self) -> dict[str, KeyBinding]:
        """Get all current bindings."""
        return dict(self._bindings)

    def get_bindings_by_category(self) -> dict[str, list[KeyBinding]]:
        """Get bindings grouped by category."""
        result: dict[str, list[KeyBinding]] = {}
        for binding in self._bindings.values():
            if binding.category not in result:
                result[binding.category] = []
            result[binding.category].append(binding)
        return result

    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a handler for an action.

        Args:
            action: The action name
            handler: The function to call
        """
        self._action_handlers[action] = handler

    def get_handler(self, action: str) -> Optional[Callable]:
        """Get the handler for an action."""
        return self._action_handlers.get(action)

    def create_prompt_toolkit_bindings(
        self,
        action_callback: Optional[Callable[[str], Any]] = None,
    ) -> KeyBindings:
        """Create prompt_toolkit KeyBindings from current bindings.

        Args:
            action_callback: Called with action name when a key is pressed
                           If provided, this is used instead of registered handlers

        Returns:
            A KeyBindings object for use with prompt_toolkit
        """
        kb = KeyBindings()

        # Map our key names to prompt_toolkit keys
        key_mapping = {
            "c-": "c-",
            "s-": "s-",
            "f1": Keys.F1,
            "f2": Keys.F2,
            "f3": Keys.F3,
            "f4": Keys.F4,
            "f5": Keys.F5,
            "f6": Keys.F6,
            "f7": Keys.F7,
            "f8": Keys.F8,
            "f9": Keys.F9,
            "f10": Keys.F10,
            "f11": Keys.F11,
            "f12": Keys.F12,
            "pageup": Keys.PageUp,
            "pagedown": Keys.PageDown,
            "home": Keys.Home,
            "end": Keys.End,
            "escape": Keys.Escape,
        }

        for key, binding in self._bindings.items():
            # Convert our key format to prompt_toolkit format
            pt_key = key
            for our_key, their_key in key_mapping.items():
                if key == our_key or key.startswith(our_key):
                    if isinstance(their_key, Keys):
                        pt_key = their_key
                    break

            # Create the handler
            action = binding.action

            def create_handler(action_name: str):
                def handler(event):
                    if action_callback:
                        action_callback(action_name)
                    elif action_name in self._action_handlers:
                        self._action_handlers[action_name]()
                return handler

            try:
                kb.add(pt_key)(create_handler(action))
            except (ValueError, KeyError) as e:
                # Some keys might not be valid in prompt_toolkit, skip them
                logger.debug(f"Could not bind key {key}: {e}")

        return kb

    def format_bindings_help(self) -> str:
        """Format bindings as a help string."""
        lines = ["Keyboard Shortcuts:", ""]
        by_category = self.get_bindings_by_category()

        category_order = ["display", "navigation", "editing", "session", "custom"]
        category_names = {
            "display": "Display",
            "navigation": "Navigation",
            "editing": "Editing",
            "session": "Session",
            "custom": "Custom",
        }

        for category in category_order:
            if category in by_category:
                bindings = by_category[category]
                lines.append(f"  {category_names.get(category, category.title())}:")
                for binding in sorted(bindings, key=lambda b: b.key):
                    lines.append(f"    {binding.display_key:15} {binding.description}")
                lines.append("")

        return "\n".join(lines)
