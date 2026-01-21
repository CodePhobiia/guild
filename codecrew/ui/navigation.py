"""Message navigation and search system for the TUI."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .components.message_list import MessageItem, MessageList


@dataclass
class SearchResult:
    """A single search result."""

    message_index: int
    match_start: int
    match_end: int
    matched_text: str


@dataclass
class NavigationState:
    """Current navigation state for the message list."""

    scroll_offset: int = 0
    selected_index: Optional[int] = None
    search_query: Optional[str] = None
    search_results: list[SearchResult] = field(default_factory=list)
    search_index: int = 0
    case_sensitive: bool = False
    viewport_height: int = 20  # Default viewport height in lines


class NavigationManager:
    """Manages message list navigation and search.

    Handles scrolling, message selection, and search functionality
    for the message display area.
    """

    def __init__(
        self,
        get_messages: Callable[[], list["MessageItem"]],
        viewport_height: int = 20,
        on_state_change: Optional[Callable[["NavigationState"], None]] = None,
    ):
        """Initialize the navigation manager.

        Args:
            get_messages: Callable that returns the current list of messages
            viewport_height: Height of the viewport in lines
            on_state_change: Callback when navigation state changes
        """
        self._get_messages = get_messages
        self._on_state_change = on_state_change
        self.state = NavigationState(viewport_height=viewport_height)

    def _notify_change(self) -> None:
        """Notify listeners of state change."""
        if self._on_state_change:
            self._on_state_change(self.state)

    @property
    def messages(self) -> list["MessageItem"]:
        """Get the current message list."""
        return self._get_messages()

    @property
    def message_count(self) -> int:
        """Get the total number of messages."""
        return len(self.messages)

    @property
    def max_scroll_offset(self) -> int:
        """Calculate maximum scroll offset."""
        # Allow scrolling so the last message can be at top
        return max(0, self.message_count - 1)

    # ========================================================================
    # Scrolling
    # ========================================================================

    def scroll_up(self, lines: int = 1) -> bool:
        """Scroll up by the specified number of lines.

        Args:
            lines: Number of lines to scroll up

        Returns:
            True if scroll position changed, False otherwise
        """
        old_offset = self.state.scroll_offset
        self.state.scroll_offset = max(0, self.state.scroll_offset - lines)
        if old_offset != self.state.scroll_offset:
            self._notify_change()
            return True
        return False

    def scroll_down(self, lines: int = 1) -> bool:
        """Scroll down by the specified number of lines.

        Args:
            lines: Number of lines to scroll down

        Returns:
            True if scroll position changed, False otherwise
        """
        old_offset = self.state.scroll_offset
        self.state.scroll_offset = min(
            self.max_scroll_offset,
            self.state.scroll_offset + lines,
        )
        if old_offset != self.state.scroll_offset:
            self._notify_change()
            return True
        return False

    def scroll_to_top(self) -> bool:
        """Scroll to the top of the message list.

        Returns:
            True if scroll position changed, False otherwise
        """
        if self.state.scroll_offset != 0:
            self.state.scroll_offset = 0
            self._notify_change()
            return True
        return False

    def scroll_to_bottom(self) -> bool:
        """Scroll to the bottom of the message list.

        Returns:
            True if scroll position changed, False otherwise
        """
        target = self.max_scroll_offset
        if self.state.scroll_offset != target:
            self.state.scroll_offset = target
            self._notify_change()
            return True
        return False

    def scroll_page_up(self) -> bool:
        """Scroll up by one page (viewport height).

        Returns:
            True if scroll position changed, False otherwise
        """
        return self.scroll_up(self.state.viewport_height)

    def scroll_page_down(self) -> bool:
        """Scroll down by one page (viewport height).

        Returns:
            True if scroll position changed, False otherwise
        """
        return self.scroll_down(self.state.viewport_height)

    def scroll_to_message(self, index: int) -> bool:
        """Scroll to bring a specific message into view.

        Args:
            index: Index of the message to scroll to

        Returns:
            True if scroll position changed, False otherwise
        """
        if index < 0 or index >= self.message_count:
            return False

        old_offset = self.state.scroll_offset

        # If message is above viewport, scroll up to it
        if index < self.state.scroll_offset:
            self.state.scroll_offset = index
        # If message is below viewport, scroll down
        elif index >= self.state.scroll_offset + self.state.viewport_height:
            self.state.scroll_offset = index - self.state.viewport_height + 1

        if old_offset != self.state.scroll_offset:
            self._notify_change()
            return True
        return False

    def set_viewport_height(self, height: int) -> None:
        """Update the viewport height.

        Args:
            height: New viewport height in lines
        """
        self.state.viewport_height = max(1, height)
        # Ensure scroll offset is still valid
        if self.state.scroll_offset > self.max_scroll_offset:
            self.state.scroll_offset = self.max_scroll_offset
            self._notify_change()

    # ========================================================================
    # Message Selection
    # ========================================================================

    def select_message(self, index: int) -> bool:
        """Select a message by index.

        Args:
            index: Index of the message to select

        Returns:
            True if selection changed, False otherwise
        """
        if index < 0 or index >= self.message_count:
            return False

        if self.state.selected_index != index:
            self.state.selected_index = index
            self.scroll_to_message(index)
            self._notify_change()
            return True
        return False

    def select_next(self) -> bool:
        """Select the next message.

        Returns:
            True if selection changed, False otherwise
        """
        if self.message_count == 0:
            return False

        if self.state.selected_index is None:
            return self.select_message(0)

        return self.select_message(self.state.selected_index + 1)

    def select_previous(self) -> bool:
        """Select the previous message.

        Returns:
            True if selection changed, False otherwise
        """
        if self.message_count == 0:
            return False

        if self.state.selected_index is None:
            return self.select_message(self.message_count - 1)

        return self.select_message(self.state.selected_index - 1)

    def clear_selection(self) -> bool:
        """Clear the current selection.

        Returns:
            True if selection was cleared, False if already clear
        """
        if self.state.selected_index is not None:
            self.state.selected_index = None
            self._notify_change()
            return True
        return False

    def get_selected_message(self) -> Optional["MessageItem"]:
        """Get the currently selected message.

        Returns:
            The selected MessageItem or None
        """
        if self.state.selected_index is not None:
            messages = self.messages
            if 0 <= self.state.selected_index < len(messages):
                return messages[self.state.selected_index]
        return None

    # ========================================================================
    # Search
    # ========================================================================

    def search(
        self,
        query: str,
        case_sensitive: bool = False,
    ) -> int:
        """Search for messages containing the query.

        Args:
            query: Search query string
            case_sensitive: Whether search is case-sensitive

        Returns:
            Number of matches found
        """
        self.state.search_query = query
        self.state.case_sensitive = case_sensitive
        self.state.search_results = []
        self.state.search_index = 0

        if not query:
            self._notify_change()
            return 0

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)

        for i, msg in enumerate(self.messages):
            content = msg.content if hasattr(msg, "content") else str(msg)
            for match in pattern.finditer(content):
                self.state.search_results.append(
                    SearchResult(
                        message_index=i,
                        match_start=match.start(),
                        match_end=match.end(),
                        matched_text=match.group(),
                    )
                )

        self._notify_change()
        return len(self.state.search_results)

    def next_match(self) -> Optional[SearchResult]:
        """Go to the next search match.

        Returns:
            The next SearchResult or None if no matches
        """
        if not self.state.search_results:
            return None

        self.state.search_index = (self.state.search_index + 1) % len(
            self.state.search_results
        )
        result = self.state.search_results[self.state.search_index]
        self.scroll_to_message(result.message_index)
        self.state.selected_index = result.message_index
        self._notify_change()
        return result

    def previous_match(self) -> Optional[SearchResult]:
        """Go to the previous search match.

        Returns:
            The previous SearchResult or None if no matches
        """
        if not self.state.search_results:
            return None

        self.state.search_index = (self.state.search_index - 1) % len(
            self.state.search_results
        )
        result = self.state.search_results[self.state.search_index]
        self.scroll_to_message(result.message_index)
        self.state.selected_index = result.message_index
        self._notify_change()
        return result

    def current_match(self) -> Optional[SearchResult]:
        """Get the current search match.

        Returns:
            The current SearchResult or None if no matches
        """
        if not self.state.search_results:
            return None
        return self.state.search_results[self.state.search_index]

    def clear_search(self) -> None:
        """Clear the current search."""
        self.state.search_query = None
        self.state.search_results = []
        self.state.search_index = 0
        self._notify_change()

    @property
    def search_match_count(self) -> int:
        """Get the number of search matches."""
        return len(self.state.search_results)

    @property
    def search_position(self) -> tuple[int, int]:
        """Get the current search position as (current, total).

        Returns:
            Tuple of (current_match_index + 1, total_matches) or (0, 0) if no search
        """
        if not self.state.search_results:
            return (0, 0)
        return (self.state.search_index + 1, len(self.state.search_results))

    # ========================================================================
    # Visibility Helpers
    # ========================================================================

    def get_visible_range(self) -> tuple[int, int]:
        """Get the range of visible message indices.

        Returns:
            Tuple of (start_index, end_index) - end is exclusive
        """
        start = self.state.scroll_offset
        end = min(
            self.message_count,
            self.state.scroll_offset + self.state.viewport_height,
        )
        return (start, end)

    def is_message_visible(self, index: int) -> bool:
        """Check if a message is currently visible.

        Args:
            index: Message index to check

        Returns:
            True if the message is in the visible viewport
        """
        start, end = self.get_visible_range()
        return start <= index < end

    def is_at_top(self) -> bool:
        """Check if scrolled to the top."""
        return self.state.scroll_offset == 0

    def is_at_bottom(self) -> bool:
        """Check if scrolled to the bottom."""
        return self.state.scroll_offset >= self.max_scroll_offset

    # ========================================================================
    # Go To
    # ========================================================================

    def goto_message(self, identifier: str) -> bool:
        """Go to a message by ID or index.

        Args:
            identifier: Message ID or numeric index

        Returns:
            True if navigation succeeded, False otherwise
        """
        # Try as numeric index first
        try:
            index = int(identifier)
            # Support negative indexing
            if index < 0:
                index = self.message_count + index
            return self.select_message(index)
        except ValueError:
            pass

        # Try as message ID
        for i, msg in enumerate(self.messages):
            if hasattr(msg, "id") and msg.id == identifier:
                return self.select_message(i)

        return False

    def goto_latest(self) -> bool:
        """Go to the latest (most recent) message.

        Returns:
            True if navigation succeeded, False otherwise
        """
        if self.message_count > 0:
            return self.select_message(self.message_count - 1)
        return False

    def goto_first(self) -> bool:
        """Go to the first message.

        Returns:
            True if navigation succeeded, False otherwise
        """
        if self.message_count > 0:
            return self.select_message(0)
        return False
