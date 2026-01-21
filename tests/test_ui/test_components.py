"""Tests for TUI components."""

from datetime import datetime

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from codecrew.models.types import ModelResponse, ToolCall, ToolResult, Usage
from codecrew.ui.components.header import CompactHeader, Header
from codecrew.ui.components.message import (
    DecisionIndicator,
    MessageRenderer,
    StreamingMessage,
)
from codecrew.ui.components.message_list import MessageItem, MessageList
from codecrew.ui.components.spinner import (
    Spinner,
    SpinnerType,
    ThinkingIndicator,
    ToolExecutingIndicator,
    TypingIndicator,
)
from codecrew.ui.components.status_bar import MiniStatus, StatusBar
from codecrew.ui.components.tool_panel import ToolCallDisplay, ToolPanel
from codecrew.ui.theme import DEFAULT_THEME


@pytest.fixture
def theme():
    """Provide default theme for tests."""
    return DEFAULT_THEME


@pytest.fixture
def console():
    """Provide Rich console for tests."""
    return Console(force_terminal=True)


class TestSpinner:
    """Tests for Spinner component."""

    def test_spinner_creation(self, theme):
        """Test spinner creation."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        assert spinner.spinner_type == SpinnerType.THINKING

    def test_spinner_frames(self, theme):
        """Test spinner has frames."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        assert len(spinner.frames) > 0

    def test_spinner_current_frame(self, theme):
        """Test current frame is from frame list."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        assert spinner.current_frame in spinner.frames

    def test_spinner_render(self, theme):
        """Test spinner renders to Text."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        result = spinner.render()
        assert isinstance(result, Text)

    def test_spinner_with_message(self, theme):
        """Test spinner with message."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        spinner.set_message("Loading...")
        result = spinner.render()
        assert "Loading..." in str(result)

    def test_spinner_with_model(self, theme):
        """Test spinner with model name."""
        spinner = Spinner(SpinnerType.THINKING, theme=theme)
        spinner.set_model("claude")
        result = spinner.render()
        assert "Claude" in str(result)


class TestThinkingIndicator:
    """Tests for ThinkingIndicator."""

    def test_thinking_indicator_creation(self, theme):
        """Test creation with models."""
        indicator = ThinkingIndicator(
            models=["claude", "gpt"],
            theme=theme,
        )
        assert indicator.models == ["claude", "gpt"]

    def test_thinking_indicator_render(self, theme):
        """Test rendering."""
        indicator = ThinkingIndicator(
            models=["claude", "gpt"],
            theme=theme,
        )
        result = indicator.render()
        assert isinstance(result, Text)
        result_str = str(result)
        assert "Claude" in result_str
        assert "GPT" in result_str


class TestTypingIndicator:
    """Tests for TypingIndicator."""

    def test_typing_indicator_creation(self, theme):
        """Test creation."""
        indicator = TypingIndicator(model="claude", theme=theme)
        assert indicator.model == "claude"

    def test_typing_indicator_render(self, theme):
        """Test rendering."""
        indicator = TypingIndicator(model="claude", theme=theme)
        result = indicator.render()
        assert "Claude" in str(result)
        assert "typing" in str(result)


class TestToolExecutingIndicator:
    """Tests for ToolExecutingIndicator."""

    def test_tool_executing_indicator_creation(self, theme):
        """Test creation."""
        indicator = ToolExecutingIndicator(
            tool_name="read_file",
            model="claude",
            theme=theme,
        )
        assert indicator.tool_name == "read_file"
        assert indicator.model == "claude"

    def test_tool_executing_indicator_render(self, theme):
        """Test rendering."""
        indicator = ToolExecutingIndicator(
            tool_name="read_file",
            model="claude",
            theme=theme,
        )
        result = indicator.render()
        result_str = str(result)
        assert "read_file" in result_str
        assert "Claude" in result_str


class TestMessageRenderer:
    """Tests for MessageRenderer."""

    def test_render_user_message(self, theme):
        """Test rendering user message."""
        renderer = MessageRenderer(theme=theme)
        panel = renderer.render_user_message("Hello!")
        assert isinstance(panel, Panel)

    def test_render_assistant_message(self, theme):
        """Test rendering assistant message."""
        renderer = MessageRenderer(theme=theme)
        panel = renderer.render_assistant_message(
            content="Hello!",
            model="claude",
        )
        assert isinstance(panel, Panel)

    def test_render_assistant_message_with_usage(self, theme):
        """Test rendering with usage info."""
        renderer = MessageRenderer(theme=theme)
        usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        panel = renderer.render_assistant_message(
            content="Hello!",
            model="claude",
            usage=usage,
        )
        assert isinstance(panel, Panel)

    def test_render_system_message(self, theme):
        """Test rendering system message."""
        renderer = MessageRenderer(theme=theme)
        panel = renderer.render_system_message("System notice")
        assert isinstance(panel, Panel)

    def test_render_error_message(self, theme):
        """Test rendering error message."""
        renderer = MessageRenderer(theme=theme)
        panel = renderer.render_error_message("Error occurred")
        assert isinstance(panel, Panel)

    def test_render_tool_call(self, theme):
        """Test rendering tool call."""
        renderer = MessageRenderer(theme=theme)
        tool_call = ToolCall(
            id="tc_123",
            name="read_file",
            arguments={"path": "/test.txt"},
        )
        panel = renderer.render_tool_call(tool_call, model="claude")
        assert isinstance(panel, Panel)

    def test_render_tool_result(self, theme):
        """Test rendering tool result."""
        renderer = MessageRenderer(theme=theme)
        tool_result = ToolResult(
            tool_call_id="tc_123",
            content="File contents here",
            is_error=False,
        )
        panel = renderer.render_tool_result(tool_result)
        assert isinstance(panel, Panel)

    def test_render_tool_result_error(self, theme):
        """Test rendering tool error."""
        renderer = MessageRenderer(theme=theme)
        tool_result = ToolResult(
            tool_call_id="tc_123",
            content="File not found",
            is_error=True,
        )
        panel = renderer.render_tool_result(tool_result)
        assert isinstance(panel, Panel)


class TestStreamingMessage:
    """Tests for StreamingMessage."""

    def test_streaming_message_creation(self, theme):
        """Test creation."""
        msg = StreamingMessage(model="claude", theme=theme)
        assert msg.model == "claude"
        assert msg.content == ""
        assert not msg.is_complete

    def test_streaming_message_append(self, theme):
        """Test appending chunks."""
        msg = StreamingMessage(model="claude", theme=theme)
        msg.append("Hello")
        msg.append(" world")
        assert msg.content == "Hello world"

    def test_streaming_message_complete(self, theme):
        """Test completing message."""
        from codecrew.models.types import FinishReason
        msg = StreamingMessage(model="claude", theme=theme)
        msg.append("Hello")
        response = ModelResponse(
            model="claude",
            content="Hello world",
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        msg.complete(response)
        assert msg.is_complete
        assert msg.content == "Hello world"
        assert msg.usage is not None

    def test_streaming_message_render(self, theme):
        """Test rendering."""
        msg = StreamingMessage(model="claude", theme=theme)
        msg.append("Hello")
        panel = msg.render()
        assert isinstance(panel, Panel)


class TestMessageItem:
    """Tests for MessageItem factory methods."""

    def test_user_item(self):
        """Test user message item."""
        item = MessageItem.user("Hello")
        assert item.type == "user"
        assert item.content == "Hello"

    def test_assistant_item(self):
        """Test assistant message item."""
        item = MessageItem.assistant("Hi", model="claude")
        assert item.type == "assistant"
        assert item.content == "Hi"
        assert item.model == "claude"

    def test_system_item(self):
        """Test system message item."""
        item = MessageItem.system("Notice")
        assert item.type == "system"
        assert item.content == "Notice"

    def test_error_item(self):
        """Test error message item."""
        item = MessageItem.error("Error", model="claude")
        assert item.type == "error"
        assert item.content == "Error"

    def test_tool_call_item(self):
        """Test tool call item."""
        tool_call = ToolCall(id="tc_1", name="test", arguments={})
        item = MessageItem.from_tool_call(tool_call, model="claude")
        assert item.type == "tool_call"
        assert item.tool_call is tool_call

    def test_tool_result_item(self):
        """Test tool result item."""
        result = ToolResult(tool_call_id="tc_1", content="result", is_error=False)
        item = MessageItem.from_tool_result(result)
        assert item.type == "tool_result"
        assert item.tool_result is result

    def test_thinking_item(self):
        """Test thinking indicator item."""
        item = MessageItem.thinking(["claude", "gpt"])
        assert item.type == "thinking"
        assert item.models == ["claude", "gpt"]

    def test_typing_item(self):
        """Test typing indicator item."""
        item = MessageItem.typing("claude")
        assert item.type == "typing"
        assert item.model == "claude"

    def test_decision_item(self):
        """Test decision item."""
        item = MessageItem.decision(
            model="claude",
            will_speak=True,
            confidence=0.9,
            reason="Relevant",
        )
        assert item.type == "decision"
        assert item.will_speak is True
        assert item.confidence == 0.9


class TestMessageList:
    """Tests for MessageList."""

    def test_message_list_creation(self, theme):
        """Test creation."""
        ml = MessageList(theme=theme)
        assert ml.message_count == 0

    def test_add_user_message(self, theme):
        """Test adding user message."""
        ml = MessageList(theme=theme)
        ml.add_user_message("Hello")
        assert ml.message_count == 1

    def test_add_assistant_message(self, theme):
        """Test adding assistant message."""
        ml = MessageList(theme=theme)
        ml.add_assistant_message("Hi", model="claude")
        assert ml.message_count == 1

    def test_add_multiple_messages(self, theme):
        """Test adding multiple messages."""
        ml = MessageList(theme=theme)
        ml.add_user_message("Hello")
        ml.add_assistant_message("Hi", model="claude")
        ml.add_user_message("How are you?")
        assert ml.message_count == 3

    def test_clear_messages(self, theme):
        """Test clearing messages."""
        ml = MessageList(theme=theme)
        ml.add_user_message("Hello")
        ml.add_assistant_message("Hi", model="claude")
        ml.clear()
        assert ml.message_count == 0

    def test_streaming(self, theme):
        """Test streaming support."""
        from codecrew.models.types import FinishReason
        ml = MessageList(theme=theme)
        streaming = ml.start_streaming("claude")
        assert ml.is_streaming
        streaming.append("Hello")
        response = ModelResponse(
            model="claude",
            content="Hello world",
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        ml.finish_streaming(response)
        assert not ml.is_streaming
        assert ml.message_count == 1

    def test_thinking_indicator(self, theme):
        """Test thinking indicator."""
        ml = MessageList(theme=theme)
        ml.start_thinking(["claude", "gpt"])
        assert ml._thinking is not None
        ml.stop_thinking()
        assert ml._thinking is None

    def test_typing_indicator(self, theme):
        """Test typing indicator."""
        ml = MessageList(theme=theme)
        ml.start_typing("claude")
        assert ml._typing is not None
        ml.stop_typing()
        assert ml._typing is None

    def test_max_messages_limit(self, theme):
        """Test max messages limit."""
        ml = MessageList(theme=theme, max_messages=3)
        for i in range(5):
            ml.add_user_message(f"Message {i}")
        assert ml.message_count == 3


class TestHeader:
    """Tests for Header component."""

    def test_header_creation(self, theme):
        """Test creation."""
        header = Header(theme=theme)
        assert header.theme is theme

    def test_header_set_session(self, theme):
        """Test setting session info."""
        header = Header(theme=theme)
        header.set_session(name="Test", session_id="abc123")
        assert header.session_name == "Test"
        assert header.session_id == "abc123"

    def test_header_set_models(self, theme):
        """Test setting models."""
        header = Header(theme=theme)
        header.set_models(["claude", "gpt"])
        assert header.available_models == ["claude", "gpt"]

    def test_header_render(self, theme):
        """Test rendering."""
        header = Header(
            theme=theme,
            session_name="Test Session",
            available_models=["claude", "gpt"],
        )
        panel = header.render()
        assert isinstance(panel, Panel)


class TestCompactHeader:
    """Tests for CompactHeader."""

    def test_compact_header_render(self, theme):
        """Test rendering."""
        header = CompactHeader(
            theme=theme,
            session_name="Test",
            available_models=["claude", "gpt"],
        )
        text = header.render()
        assert isinstance(text, Text)
        text_str = str(text)
        assert "CodeCrew" in text_str


class TestStatusBar:
    """Tests for StatusBar component."""

    def test_status_bar_creation(self, theme):
        """Test creation."""
        sb = StatusBar(theme=theme)
        assert sb.status == "idle"

    def test_status_bar_update_usage(self, theme):
        """Test updating usage."""
        sb = StatusBar(theme=theme)
        usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        sb.update_usage(usage)
        assert sb.total_tokens == 30

    def test_status_bar_add_tokens(self, theme):
        """Test adding tokens."""
        sb = StatusBar(theme=theme)
        sb.add_tokens(100)
        assert sb.total_tokens == 100

    def test_status_bar_set_status(self, theme):
        """Test setting status."""
        sb = StatusBar(theme=theme)
        sb.set_status("thinking", model="claude")
        assert sb.status == "thinking"
        assert sb.active_model == "claude"

    def test_status_bar_mark_saved(self, theme):
        """Test marking as saved."""
        sb = StatusBar(theme=theme)
        sb.mark_modified()
        assert sb.is_modified
        sb.mark_saved()
        assert not sb.is_modified
        assert sb.last_saved is not None

    def test_status_bar_reset(self, theme):
        """Test reset."""
        sb = StatusBar(theme=theme)
        sb.add_tokens(100)
        sb.set_status("thinking")
        sb.reset()
        assert sb.total_tokens == 0
        assert sb.status == "idle"

    def test_status_bar_render(self, theme):
        """Test rendering."""
        sb = StatusBar(theme=theme)
        panel = sb.render()
        assert isinstance(panel, Panel)


class TestToolPanel:
    """Tests for ToolPanel component."""

    def test_tool_panel_creation(self, theme):
        """Test creation."""
        panel = ToolPanel(theme=theme)
        assert panel.call_count == 0

    def test_tool_panel_add_call(self, theme):
        """Test adding tool call."""
        panel = ToolPanel(theme=theme)
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        display = panel.add_call(tool_call, model="claude")
        assert panel.call_count == 1
        assert isinstance(display, ToolCallDisplay)

    def test_tool_panel_update_call(self, theme):
        """Test updating tool call."""
        panel = ToolPanel(theme=theme)
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        panel.add_call(tool_call, model="claude")
        result = ToolResult(tool_call_id="tc_1", content="file contents", is_error=False)
        display = panel.update_call("tc_1", result)
        assert display is not None
        assert display.status == "success"

    def test_tool_panel_get_call(self, theme):
        """Test getting tool call."""
        panel = ToolPanel(theme=theme)
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        panel.add_call(tool_call, model="claude")
        display = panel.get_call("tc_1")
        assert display is not None
        assert display.tool_call.name == "read_file"

    def test_tool_panel_clear(self, theme):
        """Test clearing."""
        panel = ToolPanel(theme=theme)
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        panel.add_call(tool_call, model="claude")
        panel.clear()
        assert panel.call_count == 0

    def test_tool_panel_pending_count(self, theme):
        """Test pending count."""
        panel = ToolPanel(theme=theme)
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        panel.add_call(tool_call, model="claude")
        assert panel.pending_count == 1
        result = ToolResult(tool_call_id="tc_1", content="done", is_error=False)
        panel.update_call("tc_1", result)
        assert panel.pending_count == 0


class TestDecisionIndicator:
    """Tests for DecisionIndicator."""

    def test_decision_indicator_will_speak(self, theme):
        """Test will speak decision."""
        indicator = DecisionIndicator(
            model="claude",
            will_speak=True,
            confidence=0.9,
            reason="Relevant",
            is_forced=False,
            theme=theme,
        )
        text = indicator.render()
        assert isinstance(text, Text)
        text_str = str(text)
        assert "Claude" in text_str
        assert "will speak" in text_str

    def test_decision_indicator_will_stay_silent(self, theme):
        """Test will stay silent decision."""
        indicator = DecisionIndicator(
            model="gpt",
            will_speak=False,
            confidence=0.2,
            reason="Not relevant",
            is_forced=False,
            theme=theme,
        )
        text = indicator.render()
        text_str = str(text)
        assert "GPT" in text_str
        assert "staying silent" in text_str

    def test_decision_indicator_forced(self, theme):
        """Test forced speaker decision."""
        indicator = DecisionIndicator(
            model="claude",
            will_speak=True,
            confidence=1.0,
            reason="Mentioned",
            is_forced=True,
            theme=theme,
        )
        text = indicator.render()
        text_str = str(text)
        assert "@mentioned" in text_str
