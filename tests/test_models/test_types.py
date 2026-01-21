"""Tests for model types."""

import pytest

from codecrew.models.types import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    ShouldSpeakResult,
    StreamChunk,
    ToolCall,
    ToolResult,
    Usage,
    estimate_cost,
)


class TestMessage:
    """Tests for Message class."""

    def test_user_factory(self) -> None:
        """Test creating a user message."""
        msg = Message.user("Hello, world!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert msg.model is None

    def test_assistant_factory(self) -> None:
        """Test creating an assistant message."""
        msg = Message.assistant("Hi there!", model="claude")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there!"
        assert msg.model == "claude"

    def test_system_factory(self) -> None:
        """Test creating a system message."""
        msg = Message.system("You are a helpful assistant.")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant."

    def test_tool_factory(self) -> None:
        """Test creating a tool result message."""
        msg = Message.tool(
            tool_call_id="call_123",
            content="File contents here",
            name="read_file",
        )
        assert msg.role == MessageRole.TOOL
        assert msg.content == "File contents here"
        assert msg.name == "read_file"
        assert len(msg.tool_results) == 1
        assert msg.tool_results[0].tool_call_id == "call_123"

    def test_is_user_message(self) -> None:
        """Test is_user_message property."""
        user_msg = Message.user("test")
        assistant_msg = Message.assistant("test")

        assert user_msg.is_user_message is True
        assert assistant_msg.is_user_message is False

    def test_is_assistant_message(self) -> None:
        """Test is_assistant_message property."""
        user_msg = Message.user("test")
        assistant_msg = Message.assistant("test")

        assert user_msg.is_assistant_message is False
        assert assistant_msg.is_assistant_message is True


class TestToolCall:
    """Tests for ToolCall class."""

    def test_create_tool_call(self) -> None:
        """Test creating a tool call."""
        tc = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "/test/file.txt"},
        )
        assert tc.id == "call_123"
        assert tc.name == "read_file"
        assert tc.arguments["path"] == "/test/file.txt"


class TestToolResult:
    """Tests for ToolResult class."""

    def test_create_tool_result(self) -> None:
        """Test creating a tool result."""
        result = ToolResult(
            tool_call_id="call_123",
            content="File contents",
            is_error=False,
        )
        assert result.tool_call_id == "call_123"
        assert result.content == "File contents"
        assert result.is_error is False

    def test_error_result(self) -> None:
        """Test creating an error tool result."""
        result = ToolResult(
            tool_call_id="call_456",
            content="File not found",
            is_error=True,
        )
        assert result.is_error is True


class TestUsage:
    """Tests for Usage class."""

    def test_create_usage(self) -> None:
        """Test creating usage info."""
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_add_usage(self) -> None:
        """Test adding two usage objects."""
        usage1 = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

        combined = usage1 + usage2
        assert combined.prompt_tokens == 300
        assert combined.completion_tokens == 150
        assert combined.total_tokens == 450

    def test_add_usage_with_cost(self) -> None:
        """Test adding usage with cost estimates."""
        usage1 = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_estimate=0.01)
        usage2 = Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300, cost_estimate=0.02)

        combined = usage1 + usage2
        assert combined.cost_estimate == 0.03


class TestModelResponse:
    """Tests for ModelResponse class."""

    def test_create_response(self) -> None:
        """Test creating a model response."""
        response = ModelResponse(
            content="Hello!",
            model="claude",
            finish_reason=FinishReason.STOP,
        )
        assert response.content == "Hello!"
        assert response.model == "claude"
        assert response.finish_reason == FinishReason.STOP

    def test_has_tool_calls(self) -> None:
        """Test has_tool_calls property."""
        response_no_tools = ModelResponse(
            content="test",
            model="claude",
            finish_reason=FinishReason.STOP,
        )
        assert response_no_tools.has_tool_calls is False

        response_with_tools = ModelResponse(
            content="",
            model="claude",
            finish_reason=FinishReason.TOOL_USE,
            tool_calls=[ToolCall(id="1", name="test", arguments={})],
        )
        assert response_with_tools.has_tool_calls is True


class TestShouldSpeakResult:
    """Tests for ShouldSpeakResult class."""

    def test_yes_factory(self) -> None:
        """Test creating a 'yes' result."""
        result = ShouldSpeakResult.yes(confidence=0.9, reason="I have something to add")
        assert result.should_speak is True
        assert result.confidence == 0.9
        assert result.reason == "I have something to add"

    def test_no_factory(self) -> None:
        """Test creating a 'no' result."""
        result = ShouldSpeakResult.no(confidence=0.8, reason="Already covered")
        assert result.should_speak is False
        assert result.confidence == 0.8
        assert result.reason == "Already covered"


class TestStreamChunk:
    """Tests for StreamChunk class."""

    def test_text_chunk(self) -> None:
        """Test creating a text chunk."""
        chunk = StreamChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.is_complete is False

    def test_complete_chunk(self) -> None:
        """Test creating a complete chunk."""
        chunk = StreamChunk(
            is_complete=True,
            finish_reason=FinishReason.STOP,
        )
        assert chunk.is_complete is True
        assert chunk.finish_reason == FinishReason.STOP

    def test_tool_call_chunk(self) -> None:
        """Test creating a tool call chunk."""
        tc = ToolCall(id="1", name="test", arguments={})
        chunk = StreamChunk(tool_call=tc)
        assert chunk.tool_call is not None
        assert chunk.tool_call.name == "test"


class TestEstimateCost:
    """Tests for cost estimation."""

    def test_estimate_cost_known_model(self) -> None:
        """Test cost estimation for known model."""
        usage = Usage(prompt_tokens=1000000, completion_tokens=500000, total_tokens=1500000)
        cost = estimate_cost("gpt-4o", usage)
        # GPT-4o: $2.5 input + $10 output per million
        # 1M input = $2.5, 0.5M output = $5
        assert cost == pytest.approx(7.5, rel=0.01)

    def test_estimate_cost_unknown_model(self) -> None:
        """Test cost estimation for unknown model."""
        usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        cost = estimate_cost("unknown-model", usage)
        assert cost == 0.0
