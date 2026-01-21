"""Tests for the tool-enabled orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from codecrew.config import Settings
from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    StreamChunk,
    ToolCall,
    Usage,
)
from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.orchestrator.events import EventType
from codecrew.orchestrator.tool_orchestrator import (
    ToolEnabledOrchestrator,
    create_tool_enabled_orchestrator,
)
from codecrew.tools import ToolExecutor, ToolRegistry, PermissionManager
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool


class AsyncIteratorMock:
    """Mock that can be used as an async iterator."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


@pytest.fixture
def mock_client():
    """Create a mock model client."""
    client = MagicMock()
    client.is_available = True
    client.display_name = "Mock Model"
    client.color = "blue"
    client.model_id = "mock-model"
    client.count_tokens = MagicMock(return_value=100)
    return client


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings()


@pytest.fixture
def tool_registry():
    """Create a tool registry with test tools."""
    registry = ToolRegistry()

    # Add a simple test tool
    registry.register(
        Tool(
            definition=ToolDefinition(
                name="get_weather",
                description="Get weather for a location",
                parameters=[
                    ToolParameter(name="location", type="string", description="Location"),
                ],
            ),
            handler=lambda args: f"Weather in {args['location']}: Sunny, 72°F",
            permission_level=PermissionLevel.SAFE,
        )
    )

    return registry


@pytest.fixture
def tool_executor(tool_registry):
    """Create a tool executor."""
    permissions = PermissionManager(auto_approve=True)
    return ToolExecutor(registry=tool_registry, permissions=permissions)


class TestToolEnabledOrchestrator:
    """Tests for ToolEnabledOrchestrator."""

    def test_creation(self, mock_client, settings, tool_executor, tool_registry):
        """Test creating a tool-enabled orchestrator."""
        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
        )

        assert orchestrator.tool_executor is tool_executor
        assert orchestrator.tool_registry is tool_registry

    def test_get_tool_definitions(self, mock_client, settings, tool_executor, tool_registry):
        """Test getting tool definitions."""
        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
        )

        definitions = orchestrator.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_stream_response_with_tool_use(
        self, mock_client, settings, tool_executor, tool_registry
    ):
        """Test streaming response with tool execution."""
        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
        )

        # First response - model calls a tool
        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "San Francisco"},
        )

        # First stream: tool call
        stream_1_chunks = [
            StreamChunk(
                content="",
                tool_call=tool_call,
                is_complete=False,
            ),
            StreamChunk(
                content="",
                is_complete=True,
                finish_reason=FinishReason.TOOL_USE,
                usage=Usage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
            ),
        ]

        # Second stream: final answer
        stream_2_chunks = [
            StreamChunk(content="The weather in San Francisco is sunny.", is_complete=False),
            StreamChunk(
                content="",
                is_complete=True,
                finish_reason=FinishReason.STOP,
                usage=Usage(prompt_tokens=100, completion_tokens=30, total_tokens=130),
            ),
        ]

        # Use side_effect with a function that returns fresh iterators
        call_count = [0]

        def get_stream(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return AsyncIteratorMock(stream_1_chunks)
            return AsyncIteratorMock(stream_2_chunks)

        mock_client.generate_stream = MagicMock(side_effect=get_stream)

        # Process the response
        events = []
        async for event in orchestrator._stream_response(
            client=mock_client,
            model_name="mock",
            messages=[Message.user("What's the weather in SF?")],
            system=None,
        ):
            events.append(event)

        # Check events
        event_types = [e.type for e in events]

        assert EventType.TOOL_CALL in event_types
        assert EventType.TOOL_RESULT in event_types
        assert EventType.RESPONSE_CHUNK in event_types
        assert EventType.RESPONSE_COMPLETE in event_types

        # Check tool result
        tool_result_event = next(e for e in events if e.type == EventType.TOOL_RESULT)
        assert "San Francisco" in tool_result_event.tool_result.content
        assert "Sunny" in tool_result_event.tool_result.content

    @pytest.mark.asyncio
    async def test_generate_response_with_tool_use(
        self, mock_client, settings, tool_executor, tool_registry
    ):
        """Test non-streaming response with tool execution."""
        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
        )

        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "NYC"},
        )

        # First response - tool call
        mock_client.generate = AsyncMock(
            side_effect=[
                ModelResponse(
                    content="",
                    model="mock",
                    finish_reason=FinishReason.TOOL_USE,
                    tool_calls=[tool_call],
                    usage=Usage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
                ),
                ModelResponse(
                    content="The weather in NYC is nice!",
                    model="mock",
                    finish_reason=FinishReason.STOP,
                    tool_calls=[],
                    usage=Usage(prompt_tokens=100, completion_tokens=30, total_tokens=130),
                ),
            ]
        )

        events = []
        async for event in orchestrator._generate_response(
            client=mock_client,
            model_name="mock",
            messages=[Message.user("Weather in NYC?")],
            system=None,
        ):
            events.append(event)

        event_types = [e.type for e in events]

        assert EventType.TOOL_CALL in event_types
        assert EventType.TOOL_RESULT in event_types
        assert EventType.RESPONSE_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_max_tool_iterations(
        self, mock_client, settings, tool_executor, tool_registry
    ):
        """Test that max tool iterations prevents infinite loops."""
        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
            max_tool_iterations=2,
        )

        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "Test"},
        )

        # Always return tool use (would cause infinite loop without limit)
        mock_client.generate = AsyncMock(
            return_value=ModelResponse(
                content="",
                model="mock",
                finish_reason=FinishReason.TOOL_USE,
                tool_calls=[tool_call],
            )
        )

        events = []
        async for event in orchestrator._generate_response(
            client=mock_client,
            model_name="mock",
            messages=[Message.user("Test")],
            system=None,
        ):
            events.append(event)

        # Should have error event due to max iterations
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert "Maximum tool iterations" in error_events[0].error

    @pytest.mark.asyncio
    async def test_tool_execution_failure(
        self, mock_client, settings, tool_registry
    ):
        """Test handling of tool execution failures."""
        # Create registry with a tool that will fail
        registry = ToolRegistry()
        registry.register(
            Tool(
                definition=ToolDefinition(
                    name="failing_tool",
                    description="A tool that fails",
                    parameters=[],
                ),
                handler=lambda args: exec("raise ValueError('Tool failed!')"),
                permission_level=PermissionLevel.SAFE,
            )
        )

        permissions = PermissionManager(auto_approve=True)
        executor = ToolExecutor(registry=registry, permissions=permissions)

        orchestrator = ToolEnabledOrchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=executor,
            tool_registry=registry,
        )

        tool_call = ToolCall(
            id="call_123",
            name="failing_tool",
            arguments={},
        )

        mock_client.generate = AsyncMock(
            side_effect=[
                ModelResponse(
                    content="",
                    model="mock",
                    finish_reason=FinishReason.TOOL_USE,
                    tool_calls=[tool_call],
                ),
                ModelResponse(
                    content="I see the tool failed.",
                    model="mock",
                    finish_reason=FinishReason.STOP,
                ),
            ]
        )

        events = []
        async for event in orchestrator._generate_response(
            client=mock_client,
            model_name="mock",
            messages=[Message.user("Test")],
            system=None,
        ):
            events.append(event)

        # Should still complete, with error in tool result
        tool_result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_result_events) == 1
        assert tool_result_events[0].tool_result.is_error


class TestToolEnabledOrchestratorFactory:
    """Tests for the factory function."""

    def test_create_tool_enabled_orchestrator(
        self, mock_client, settings, tool_executor, tool_registry
    ):
        """Test the factory function."""
        orchestrator = create_tool_enabled_orchestrator(
            clients={"mock": mock_client},
            settings=settings,
            tool_executor=tool_executor,
            tool_registry=tool_registry,
            max_tool_iterations=5,
        )

        assert isinstance(orchestrator, ToolEnabledOrchestrator)
        assert orchestrator.max_tool_iterations == 5
