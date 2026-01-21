"""Tests for TUI handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from codecrew.models.types import ModelResponse, ToolCall, ToolResult, Usage
from codecrew.orchestrator.events import EventType, OrchestratorEvent, SpeakerDecision
from codecrew.ui.components.message_list import MessageList
from codecrew.ui.components.status_bar import StatusBar
from codecrew.ui.components.tool_panel import ToolPanel
from codecrew.ui.handlers.commands import Command, CommandHandler, CommandResult
from codecrew.ui.handlers.events import EventHandler, StreamingEventBuffer
from codecrew.ui.theme import DEFAULT_THEME


@pytest.fixture
def theme():
    """Provide default theme."""
    return DEFAULT_THEME


@pytest.fixture
def message_list(theme):
    """Provide MessageList instance."""
    return MessageList(theme=theme)


@pytest.fixture
def status_bar(theme):
    """Provide StatusBar instance."""
    return StatusBar(theme=theme)


@pytest.fixture
def tool_panel(theme):
    """Provide ToolPanel instance."""
    return ToolPanel(theme=theme)


@pytest.fixture
def event_handler(message_list, status_bar, tool_panel):
    """Provide EventHandler instance."""
    return EventHandler(
        message_list=message_list,
        status_bar=status_bar,
        tool_panel=tool_panel,
    )


class TestEventHandler:
    """Tests for EventHandler."""

    @pytest.mark.asyncio
    async def test_handle_thinking(self, event_handler, status_bar):
        """Test THINKING event handling."""
        event = OrchestratorEvent.thinking()
        await event_handler.handle(event)
        assert status_bar.status == "thinking"

    @pytest.mark.asyncio
    async def test_handle_evaluating(self, event_handler, status_bar):
        """Test EVALUATING event handling."""
        event = OrchestratorEvent.evaluating("claude")
        await event_handler.handle(event)
        assert status_bar.active_model == "claude"

    @pytest.mark.asyncio
    async def test_handle_will_speak(self, event_handler, message_list):
        """Test WILL_SPEAK event handling."""
        message_list.show_decisions = True
        decision = SpeakerDecision.speak("claude", 0.9, "Relevant")
        event = OrchestratorEvent.will_speak(decision)
        await event_handler.handle(event)
        # Decision should be added to message list
        assert message_list.message_count == 1

    @pytest.mark.asyncio
    async def test_handle_will_stay_silent(self, event_handler, message_list):
        """Test WILL_STAY_SILENT event handling."""
        message_list.show_decisions = True
        decision = SpeakerDecision.silent("gpt", 0.2, "Not relevant")
        event = OrchestratorEvent.will_stay_silent(decision)
        await event_handler.handle(event)
        assert message_list.message_count == 1

    @pytest.mark.asyncio
    async def test_handle_response_start(self, event_handler, status_bar, message_list):
        """Test RESPONSE_START event handling."""
        message_list.start_thinking(["claude"])
        event = OrchestratorEvent.response_start("claude")
        await event_handler.handle(event)
        assert status_bar.status == "streaming"
        assert status_bar.active_model == "claude"
        assert message_list._thinking is None  # Cleared

    @pytest.mark.asyncio
    async def test_handle_response_chunk(self, event_handler, message_list):
        """Test RESPONSE_CHUNK event handling."""
        # Start streaming first
        message_list.start_streaming("claude")
        event = OrchestratorEvent.response_chunk("claude", "Hello")
        await event_handler.handle(event)
        assert message_list._streaming.content == "Hello"

    @pytest.mark.asyncio
    async def test_handle_response_complete(self, event_handler, status_bar, message_list):
        """Test RESPONSE_COMPLETE event handling."""
        from codecrew.models.types import FinishReason
        message_list.start_streaming("claude")
        message_list._streaming.append("Hello")
        response = ModelResponse(
            model="claude",
            content="Hello world",
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        event = OrchestratorEvent.response_complete("claude", response)
        await event_handler.handle(event)
        assert status_bar.status == "idle"
        assert message_list.message_count == 1

    @pytest.mark.asyncio
    async def test_handle_tool_call(self, event_handler, message_list, tool_panel):
        """Test TOOL_CALL event handling."""
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={"path": "/test"})
        event = OrchestratorEvent.tool_call_event("claude", tool_call)
        await event_handler.handle(event)
        assert message_list.message_count == 1
        assert tool_panel.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_tool_executing(self, event_handler, status_bar, message_list):
        """Test TOOL_EXECUTING event handling."""
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        event = OrchestratorEvent.tool_executing_event("claude", tool_call)
        await event_handler.handle(event)
        assert message_list._tool_executing is not None
        assert status_bar.status == "thinking"

    @pytest.mark.asyncio
    async def test_handle_tool_result(self, event_handler, message_list, tool_panel, status_bar):
        """Test TOOL_RESULT event handling."""
        # Add tool call first
        tool_call = ToolCall(id="tc_1", name="read_file", arguments={})
        tool_panel.add_call(tool_call, model="claude")
        message_list.start_tool_executing("read_file", "claude")

        # Now handle result
        result = ToolResult(tool_call_id="tc_1", content="file contents", is_error=False)
        event = OrchestratorEvent.tool_result_event("claude", result)
        await event_handler.handle(event)
        assert message_list._tool_executing is None
        assert message_list.message_count == 1
        assert status_bar.status == "idle"

    @pytest.mark.asyncio
    async def test_handle_error(self, event_handler, message_list, status_bar):
        """Test ERROR event handling."""
        event = OrchestratorEvent.error_event("Something went wrong", model="claude")
        await event_handler.handle(event)
        assert message_list.message_count == 1
        assert status_bar.status == "error"

    @pytest.mark.asyncio
    async def test_handle_turn_complete(self, event_handler, status_bar):
        """Test TURN_COMPLETE event handling."""
        from codecrew.models.types import FinishReason
        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        response = ModelResponse(
            model="claude",
            content="Hello",
            finish_reason=FinishReason.STOP,
            usage=usage,
        )
        event = OrchestratorEvent.turn_complete([response], usage)
        await event_handler.handle(event)
        assert status_bar.status == "idle"
        assert status_bar.is_modified

    @pytest.mark.asyncio
    async def test_error_callback(self, message_list, status_bar, tool_panel):
        """Test error callback is called."""
        errors = []
        handler = EventHandler(
            message_list=message_list,
            status_bar=status_bar,
            tool_panel=tool_panel,
            on_error=lambda e: errors.append(e),
        )
        event = OrchestratorEvent.error_event("Test error")
        await handler.handle(event)
        assert len(errors) == 1
        assert errors[0] == "Test error"


class TestStreamingEventBuffer:
    """Tests for StreamingEventBuffer."""

    def test_buffer_creation(self):
        """Test buffer creation."""
        buffer = StreamingEventBuffer()
        assert buffer.flush_interval == 0.05

    def test_add_chunk(self):
        """Test adding chunks."""
        buffer = StreamingEventBuffer()
        buffer.add_chunk("claude", "Hello")
        buffer.add_chunk("claude", " world")
        assert buffer._buffer["claude"] == "Hello world"

    def test_should_flush(self):
        """Test flush timing."""
        buffer = StreamingEventBuffer(flush_interval=0.1)
        # Initially should NOT flush (time=0, last_flush=0, interval=0.1)
        assert not buffer.should_flush(0.0)
        # Should flush after interval has passed
        assert buffer.should_flush(0.1)
        # After flush at 0.1, shouldn't flush immediately
        buffer.flush(0.1)
        assert not buffer.should_flush(0.15)
        # But should flush after interval
        assert buffer.should_flush(0.25)

    def test_flush(self):
        """Test flushing."""
        buffer = StreamingEventBuffer()
        buffer.add_chunk("claude", "Hello")
        buffer.add_chunk("gpt", "Hi")
        result = buffer.flush(1.0)
        assert result == {"claude": "Hello", "gpt": "Hi"}
        assert len(buffer._buffer) == 0

    def test_clear(self):
        """Test clearing."""
        buffer = StreamingEventBuffer()
        buffer.add_chunk("claude", "Hello")
        buffer.clear()
        assert len(buffer._buffer) == 0


class TestCommand:
    """Tests for Command dataclass."""

    def test_command_matches_name(self):
        """Test command matches its name."""
        cmd = Command(
            name="/help",
            aliases=["/h"],
            description="Show help",
            usage="/help",
            handler=AsyncMock(),
        )
        assert cmd.matches("/help")
        assert cmd.matches("/HELP")

    def test_command_matches_alias(self):
        """Test command matches aliases."""
        cmd = Command(
            name="/help",
            aliases=["/h", "/?"],
            description="Show help",
            usage="/help",
            handler=AsyncMock(),
        )
        assert cmd.matches("/h")
        assert cmd.matches("/?")

    def test_command_no_match(self):
        """Test command doesn't match others."""
        cmd = Command(
            name="/help",
            aliases=["/h"],
            description="Show help",
            usage="/help",
            handler=AsyncMock(),
        )
        assert not cmd.matches("/quit")
        assert not cmd.matches("/other")


class TestCommandHandler:
    """Tests for CommandHandler."""

    @pytest.fixture
    def mock_app(self):
        """Create mock ChatApp."""
        app = MagicMock()
        app.console = MagicMock()
        app.current_theme = "default"
        app.compact_mode = False
        app.show_decisions = False
        app.get_available_models = MagicMock(return_value=["claude", "gpt"])
        app.get_config = MagicMock(return_value={
            "theme": "default",
            "first_responder": "rotate",
        })
        return app

    def test_is_command(self, mock_app):
        """Test command detection."""
        handler = CommandHandler(mock_app)
        assert handler.is_command("/help")
        assert handler.is_command("/quit")
        assert not handler.is_command("hello")
        assert not handler.is_command("@claude")

    def test_parse_command(self, mock_app):
        """Test command parsing."""
        handler = CommandHandler(mock_app)
        cmd, args = handler.parse_command("/load abc123")
        assert cmd == "/load"
        assert args == ["abc123"]

    def test_parse_command_no_args(self, mock_app):
        """Test parsing command without args."""
        handler = CommandHandler(mock_app)
        cmd, args = handler.parse_command("/help")
        assert cmd == "/help"
        assert args == []

    @pytest.mark.asyncio
    async def test_execute_help(self, mock_app):
        """Test executing help command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/help")
        assert result == CommandResult.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_quit(self, mock_app):
        """Test executing quit command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/quit")
        assert result == CommandResult.EXIT

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self, mock_app):
        """Test executing unknown command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/unknown")
        assert result == CommandResult.ERROR

    @pytest.mark.asyncio
    async def test_execute_clear(self, mock_app):
        """Test executing clear command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/clear")
        assert result == CommandResult.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_models(self, mock_app):
        """Test executing models command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/models")
        assert result == CommandResult.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_config(self, mock_app):
        """Test executing config command."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/config")
        assert result == CommandResult.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_missing_args(self, mock_app):
        """Test executing command with missing required args."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/load")  # Requires session_id
        assert result == CommandResult.ERROR

    @pytest.mark.asyncio
    async def test_execute_compact_toggle(self, mock_app):
        """Test compact mode toggle."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/compact")
        assert result == CommandResult.SUCCESS
        mock_app.toggle_compact_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_decisions_toggle(self, mock_app):
        """Test decisions toggle."""
        handler = CommandHandler(mock_app)
        result = await handler.execute("/decisions")
        assert result == CommandResult.SUCCESS
        mock_app.toggle_show_decisions.assert_called_once()
