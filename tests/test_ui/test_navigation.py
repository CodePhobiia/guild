"""Tests for the navigation module."""

from dataclasses import dataclass
from typing import Optional

import pytest

from codecrew.ui.navigation import NavigationManager, NavigationState, SearchResult


@dataclass
class MockMessage:
    """Mock message for testing."""

    id: str
    content: str
    role: str = "assistant"


class TestNavigationState:
    """Tests for NavigationState dataclass."""

    def test_default_state(self):
        """Test default navigation state."""
        state = NavigationState()

        assert state.scroll_offset == 0
        assert state.selected_index is None
        assert state.search_query is None
        assert state.search_results == []
        assert state.search_index == 0
        assert state.case_sensitive is False
        assert state.viewport_height == 20

    def test_custom_viewport_height(self):
        """Test custom viewport height."""
        state = NavigationState(viewport_height=50)
        assert state.viewport_height == 50


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        result = SearchResult(
            message_index=5,
            match_start=10,
            match_end=15,
            matched_text="hello",
        )

        assert result.message_index == 5
        assert result.match_start == 10
        assert result.match_end == 15
        assert result.matched_text == "hello"


class TestNavigationManager:
    """Tests for NavigationManager class."""

    @pytest.fixture
    def messages(self):
        """Create a list of mock messages."""
        return [
            MockMessage(id=f"msg-{i}", content=f"Message {i} content")
            for i in range(50)
        ]

    @pytest.fixture
    def manager(self, messages):
        """Create a NavigationManager instance."""
        return NavigationManager(
            get_messages=lambda: messages,
            viewport_height=20,
        )

    def test_init(self, manager):
        """Test initialization."""
        assert manager.state.scroll_offset == 0
        assert manager.state.viewport_height == 20

    def test_message_count(self, manager):
        """Test message count property."""
        assert manager.message_count == 50

    def test_max_scroll_offset(self, manager):
        """Test max scroll offset calculation."""
        assert manager.max_scroll_offset == 49

    # Scrolling tests

    def test_scroll_down(self, manager):
        """Test scrolling down."""
        result = manager.scroll_down(5)
        assert result is True
        assert manager.state.scroll_offset == 5

    def test_scroll_down_at_bottom(self, manager):
        """Test scrolling down at bottom."""
        manager.state.scroll_offset = 49
        result = manager.scroll_down(5)
        assert result is False
        assert manager.state.scroll_offset == 49

    def test_scroll_up(self, manager):
        """Test scrolling up."""
        manager.state.scroll_offset = 10
        result = manager.scroll_up(5)
        assert result is True
        assert manager.state.scroll_offset == 5

    def test_scroll_up_at_top(self, manager):
        """Test scrolling up at top."""
        result = manager.scroll_up(5)
        assert result is False
        assert manager.state.scroll_offset == 0

    def test_scroll_to_top(self, manager):
        """Test scroll to top."""
        manager.state.scroll_offset = 30
        result = manager.scroll_to_top()
        assert result is True
        assert manager.state.scroll_offset == 0

    def test_scroll_to_top_already_at_top(self, manager):
        """Test scroll to top when already there."""
        result = manager.scroll_to_top()
        assert result is False

    def test_scroll_to_bottom(self, manager):
        """Test scroll to bottom."""
        result = manager.scroll_to_bottom()
        assert result is True
        assert manager.state.scroll_offset == 49

    def test_scroll_to_bottom_already_at_bottom(self, manager):
        """Test scroll to bottom when already there."""
        manager.state.scroll_offset = 49
        result = manager.scroll_to_bottom()
        assert result is False

    def test_scroll_page_up(self, manager):
        """Test scroll page up."""
        manager.state.scroll_offset = 30
        manager.scroll_page_up()
        assert manager.state.scroll_offset == 10

    def test_scroll_page_down(self, manager):
        """Test scroll page down."""
        manager.scroll_page_down()
        assert manager.state.scroll_offset == 20

    def test_scroll_to_message(self, manager):
        """Test scrolling to a specific message."""
        result = manager.scroll_to_message(25)
        assert result is True
        # Message 25 should be visible in viewport

    def test_scroll_to_message_invalid_index(self, manager):
        """Test scrolling to invalid message index."""
        result = manager.scroll_to_message(100)
        assert result is False

        result = manager.scroll_to_message(-1)
        assert result is False

    def test_set_viewport_height(self, manager):
        """Test setting viewport height."""
        manager.set_viewport_height(30)
        assert manager.state.viewport_height == 30

    def test_set_viewport_height_minimum(self, manager):
        """Test viewport height minimum."""
        manager.set_viewport_height(0)
        assert manager.state.viewport_height == 1

    # Selection tests

    def test_select_message(self, manager):
        """Test selecting a message."""
        result = manager.select_message(10)
        assert result is True
        assert manager.state.selected_index == 10

    def test_select_message_invalid(self, manager):
        """Test selecting invalid message."""
        result = manager.select_message(100)
        assert result is False
        assert manager.state.selected_index is None

    def test_select_next(self, manager):
        """Test selecting next message."""
        manager.select_message(5)
        result = manager.select_next()
        assert result is True
        assert manager.state.selected_index == 6

    def test_select_next_from_none(self, manager):
        """Test selecting next when nothing selected."""
        result = manager.select_next()
        assert result is True
        assert manager.state.selected_index == 0

    def test_select_previous(self, manager):
        """Test selecting previous message."""
        manager.select_message(5)
        result = manager.select_previous()
        assert result is True
        assert manager.state.selected_index == 4

    def test_select_previous_from_none(self, manager):
        """Test selecting previous when nothing selected."""
        result = manager.select_previous()
        assert result is True
        assert manager.state.selected_index == 49  # Last message

    def test_clear_selection(self, manager):
        """Test clearing selection."""
        manager.select_message(10)
        result = manager.clear_selection()
        assert result is True
        assert manager.state.selected_index is None

    def test_clear_selection_already_clear(self, manager):
        """Test clearing selection when already clear."""
        result = manager.clear_selection()
        assert result is False

    def test_get_selected_message(self, manager, messages):
        """Test getting selected message."""
        manager.select_message(5)
        msg = manager.get_selected_message()
        assert msg is not None
        assert msg.id == "msg-5"

    def test_get_selected_message_none(self, manager):
        """Test getting selected message when none selected."""
        msg = manager.get_selected_message()
        assert msg is None

    # Search tests

    def test_search(self, manager):
        """Test searching messages."""
        count = manager.search("Message 1")
        # Should match Message 1, 10-19
        assert count > 0

    def test_search_no_results(self, manager):
        """Test search with no results."""
        count = manager.search("xyz123nonexistent")
        assert count == 0

    def test_search_case_insensitive(self, manager):
        """Test case-insensitive search."""
        count1 = manager.search("message", case_sensitive=False)
        count2 = manager.search("MESSAGE", case_sensitive=False)
        assert count1 == count2

    def test_search_case_sensitive(self, manager):
        """Test case-sensitive search."""
        count_lower = manager.search("message", case_sensitive=True)
        count_upper = manager.search("MESSAGE", case_sensitive=True)
        # Should be different if content uses different case
        assert count_upper == 0

    def test_next_match(self, manager):
        """Test navigating to next match."""
        manager.search("Message")
        result = manager.next_match()
        assert result is not None
        assert isinstance(result, SearchResult)

    def test_next_match_wraps(self, manager):
        """Test that next match wraps around."""
        manager.search("Message 1 content")  # Should match exactly one
        first_result = manager.current_match()
        manager.next_match()
        # Should wrap to first result
        assert manager.current_match() is not None

    def test_previous_match(self, manager):
        """Test navigating to previous match."""
        manager.search("Message")
        manager.next_match()
        manager.next_match()
        result = manager.previous_match()
        assert result is not None

    def test_current_match(self, manager):
        """Test getting current match."""
        manager.search("Message")
        result = manager.current_match()
        assert result is not None

    def test_current_match_no_search(self, manager):
        """Test getting current match without search."""
        result = manager.current_match()
        assert result is None

    def test_clear_search(self, manager):
        """Test clearing search."""
        manager.search("Message")
        manager.clear_search()
        assert manager.state.search_query is None
        assert manager.state.search_results == []

    def test_search_match_count(self, manager):
        """Test search match count."""
        manager.search("Message")
        assert manager.search_match_count == 50  # All messages match

    def test_search_position(self, manager):
        """Test search position."""
        manager.search("Message")
        pos = manager.search_position
        assert pos[0] == 1  # First match (1-indexed)
        assert pos[1] == 50  # Total matches

    def test_search_position_no_search(self, manager):
        """Test search position without search."""
        pos = manager.search_position
        assert pos == (0, 0)

    # Visibility tests

    def test_get_visible_range(self, manager):
        """Test getting visible range."""
        start, end = manager.get_visible_range()
        assert start == 0
        assert end == 20

    def test_get_visible_range_scrolled(self, manager):
        """Test visible range when scrolled."""
        manager.scroll_down(10)
        start, end = manager.get_visible_range()
        assert start == 10
        assert end == 30

    def test_is_message_visible(self, manager):
        """Test checking if message is visible."""
        assert manager.is_message_visible(0) is True
        assert manager.is_message_visible(19) is True
        assert manager.is_message_visible(20) is False
        assert manager.is_message_visible(30) is False

    def test_is_at_top(self, manager):
        """Test checking if at top."""
        assert manager.is_at_top() is True
        manager.scroll_down(10)
        assert manager.is_at_top() is False

    def test_is_at_bottom(self, manager):
        """Test checking if at bottom."""
        assert manager.is_at_bottom() is False
        manager.scroll_to_bottom()
        assert manager.is_at_bottom() is True

    # Goto tests

    def test_goto_message_by_index(self, manager):
        """Test goto message by numeric index."""
        result = manager.goto_message("25")
        assert result is True
        assert manager.state.selected_index == 25

    def test_goto_message_negative_index(self, manager):
        """Test goto message with negative index."""
        result = manager.goto_message("-1")
        assert result is True
        assert manager.state.selected_index == 49

    def test_goto_message_by_id(self, manager):
        """Test goto message by ID."""
        result = manager.goto_message("msg-10")
        assert result is True
        assert manager.state.selected_index == 10

    def test_goto_message_invalid(self, manager):
        """Test goto invalid message."""
        result = manager.goto_message("invalid-id")
        assert result is False

    def test_goto_latest(self, manager):
        """Test goto latest message."""
        result = manager.goto_latest()
        assert result is True
        assert manager.state.selected_index == 49

    def test_goto_first(self, manager):
        """Test goto first message."""
        manager.select_message(25)
        result = manager.goto_first()
        assert result is True
        assert manager.state.selected_index == 0

    # Callback tests

    def test_state_change_callback(self):
        """Test that state change callback is called."""
        changes = []

        def on_change(state):
            changes.append(state.scroll_offset)

        messages = [MockMessage(id=f"msg-{i}", content=f"Message {i}") for i in range(50)]
        manager = NavigationManager(
            get_messages=lambda: messages,
            viewport_height=20,
            on_state_change=on_change,
        )

        manager.scroll_down(5)
        manager.scroll_down(5)

        assert len(changes) == 2
        assert changes == [5, 10]


class TestEmptyMessageList:
    """Tests for empty message list edge cases."""

    @pytest.fixture
    def manager(self):
        """Create a manager with empty message list."""
        return NavigationManager(
            get_messages=lambda: [],
            viewport_height=20,
        )

    def test_message_count_empty(self, manager):
        """Test message count with empty list."""
        assert manager.message_count == 0

    def test_max_scroll_offset_empty(self, manager):
        """Test max scroll offset with empty list."""
        assert manager.max_scroll_offset == 0

    def test_select_next_empty(self, manager):
        """Test select next with empty list."""
        result = manager.select_next()
        assert result is False

    def test_select_previous_empty(self, manager):
        """Test select previous with empty list."""
        result = manager.select_previous()
        assert result is False

    def test_search_empty(self, manager):
        """Test search with empty list."""
        count = manager.search("test")
        assert count == 0

    def test_goto_latest_empty(self, manager):
        """Test goto latest with empty list."""
        result = manager.goto_latest()
        assert result is False

    def test_goto_first_empty(self, manager):
        """Test goto first with empty list."""
        result = manager.goto_first()
        assert result is False
