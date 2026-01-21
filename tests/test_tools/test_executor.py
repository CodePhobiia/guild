"""Tests for the tool executor."""

import asyncio

import pytest

from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.models.types import ToolCall
from codecrew.tools.executor import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutor,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
)
from codecrew.tools.permissions import PermissionLevel, PermissionManager
from codecrew.tools.registry import Tool, ToolRegistry


@pytest.fixture
def registry():
    """Create a tool registry with test tools."""
    reg = ToolRegistry()

    # Simple sync tool
    reg.register(
        Tool(
            definition=ToolDefinition(
                name="echo",
                description="Echo the input",
                parameters=[
                    ToolParameter(name="message", type="string", description="Message to echo"),
                ],
            ),
            handler=lambda args: f"Echo: {args['message']}",
            permission_level=PermissionLevel.SAFE,
        )
    )

    # Async tool
    async def async_handler(args):
        await asyncio.sleep(0.01)
        return f"Async: {args['value']}"

    reg.register(
        Tool(
            definition=ToolDefinition(
                name="async_tool",
                description="An async tool",
                parameters=[
                    ToolParameter(name="value", type="string", description="Value"),
                ],
            ),
            handler=async_handler,
            permission_level=PermissionLevel.SAFE,
        )
    )

    # Tool that raises error
    def error_handler(args):
        raise ValueError("Intentional error")

    reg.register(
        Tool(
            definition=ToolDefinition(
                name="error_tool",
                description="A tool that errors",
                parameters=[],
            ),
            handler=error_handler,
            permission_level=PermissionLevel.SAFE,
        )
    )

    # Slow tool for timeout testing
    async def slow_handler(args):
        await asyncio.sleep(10)
        return "Done"

    reg.register(
        Tool(
            definition=ToolDefinition(
                name="slow_tool",
                description="A slow tool",
                parameters=[],
            ),
            handler=slow_handler,
            permission_level=PermissionLevel.SAFE,
            timeout=0.1,  # Very short timeout
        )
    )

    # Cautious tool
    reg.register(
        Tool(
            definition=ToolDefinition(
                name="cautious_tool",
                description="A cautious tool",
                parameters=[],
            ),
            handler=lambda args: "cautious result",
            permission_level=PermissionLevel.CAUTIOUS,
        )
    )

    # Tool with enum parameter
    reg.register(
        Tool(
            definition=ToolDefinition(
                name="enum_tool",
                description="Tool with enum parameter",
                parameters=[
                    ToolParameter(
                        name="mode",
                        type="string",
                        description="Mode",
                        enum=["read", "write", "append"],
                    ),
                ],
            ),
            handler=lambda args: f"Mode: {args['mode']}",
            permission_level=PermissionLevel.SAFE,
        )
    )

    return reg


@pytest.fixture
def permissions():
    """Create a permission manager."""
    return PermissionManager(auto_approve=True)


@pytest.fixture
def executor(registry, permissions):
    """Create a tool executor."""
    return ToolExecutor(registry=registry, permissions=permissions)


class TestToolExecutionResult:
    """Tests for ToolExecutionResult."""

    def test_successful_result(self):
        """Test a successful execution result."""
        result = ToolExecutionResult(
            tool_call_id="call_123",
            tool_name="echo",
            success=True,
            result="Hello, World!",
            execution_time=0.5,
        )

        assert result.success is True
        assert result.error is None

        tool_result = result.to_tool_result()
        assert tool_result.tool_call_id == "call_123"
        assert tool_result.content == "Hello, World!"
        assert tool_result.is_error is False

    def test_failed_result(self):
        """Test a failed execution result."""
        result = ToolExecutionResult(
            tool_call_id="call_123",
            tool_name="error_tool",
            success=False,
            error="Something went wrong",
            execution_time=0.1,
        )

        assert result.success is False
        assert result.error == "Something went wrong"

        tool_result = result.to_tool_result()
        assert tool_result.is_error is True
        assert "Error: Something went wrong" in tool_result.content

    def test_format_dict_result(self):
        """Test formatting dict results."""
        result = ToolExecutionResult(
            tool_call_id="call_123",
            tool_name="test",
            success=True,
            result={"key": "value", "count": 42},
        )

        tool_result = result.to_tool_result()
        assert '"key": "value"' in tool_result.content
        assert '"count": 42' in tool_result.content

    def test_format_list_result(self):
        """Test formatting list results."""
        result = ToolExecutionResult(
            tool_call_id="call_123",
            tool_name="test",
            success=True,
            result=["item1", "item2", "item3"],
        )

        tool_result = result.to_tool_result()
        assert "item1" in tool_result.content

    def test_format_none_result(self):
        """Test formatting None result."""
        result = ToolExecutionResult(
            tool_call_id="call_123",
            tool_name="test",
            success=True,
            result=None,
        )

        tool_result = result.to_tool_result()
        assert "Success" in tool_result.content


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self, executor):
        """Test executing a synchronous tool."""
        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments={"message": "Hello"},
        )

        result = await executor.execute(tool_call)

        assert result.success is True
        assert result.result == "Echo: Hello"
        assert result.tool_name == "echo"

    @pytest.mark.asyncio
    async def test_execute_async_tool(self, executor):
        """Test executing an asynchronous tool."""
        tool_call = ToolCall(
            id="call_123",
            name="async_tool",
            arguments={"value": "test"},
        )

        result = await executor.execute(tool_call)

        assert result.success is True
        assert result.result == "Async: test"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, executor):
        """Test executing an unknown tool."""
        tool_call = ToolCall(
            id="call_123",
            name="unknown_tool",
            arguments={},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_disabled_tool(self, executor, registry):
        """Test executing a disabled tool."""
        registry.disable("echo")

        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments={"message": "test"},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, executor):
        """Test executing a tool that raises an error."""
        tool_call = ToolCall(
            id="call_123",
            name="error_tool",
            arguments={},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "Intentional error" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_timeout(self, executor):
        """Test that slow tools timeout."""
        tool_call = ToolCall(
            id="call_123",
            name="slow_tool",
            arguments={},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_missing_required_param(self, executor):
        """Test validation for missing required parameter."""
        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments={},  # Missing 'message'
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "missing required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_unknown_param(self, executor):
        """Test validation for unknown parameter."""
        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments={"message": "test", "unknown": "param"},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "unknown parameter" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_invalid_enum(self, executor):
        """Test validation for invalid enum value."""
        tool_call = ToolCall(
            id="call_123",
            name="enum_tool",
            arguments={"mode": "invalid"},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "must be one of" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validation_invalid_type(self, executor):
        """Test validation for invalid type."""
        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments={"message": 123},  # Should be string
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "invalid type" in result.error.lower()

    @pytest.mark.asyncio
    async def test_permission_denied(self, registry):
        """Test permission denied for cautious tool."""
        permissions = PermissionManager()  # No auto-approve

        executor = ToolExecutor(registry=registry, permissions=permissions)

        tool_call = ToolCall(
            id="call_123",
            name="cautious_tool",
            arguments={},
        )

        result = await executor.execute(tool_call)

        assert result.success is False
        assert "permission" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_batch_sequential(self, executor):
        """Test executing multiple tools sequentially."""
        tool_calls = [
            ToolCall(id="call_1", name="echo", arguments={"message": "one"}),
            ToolCall(id="call_2", name="echo", arguments={"message": "two"}),
            ToolCall(id="call_3", name="echo", arguments={"message": "three"}),
        ]

        results = await executor.execute_batch(tool_calls, parallel=False)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].result == "Echo: one"
        assert results[1].result == "Echo: two"
        assert results[2].result == "Echo: three"

    @pytest.mark.asyncio
    async def test_execute_batch_parallel(self, executor):
        """Test executing multiple tools in parallel."""
        tool_calls = [
            ToolCall(id="call_1", name="async_tool", arguments={"value": "one"}),
            ToolCall(id="call_2", name="async_tool", arguments={"value": "two"}),
        ]

        results = await executor.execute_batch(tool_calls, parallel=True)

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_get_tool_results(self, executor):
        """Test converting execution results to tool results."""
        tool_calls = [
            ToolCall(id="call_1", name="echo", arguments={"message": "test"}),
        ]

        results = await executor.execute_batch(tool_calls)
        tool_results = executor.get_tool_results(results)

        assert len(tool_results) == 1
        assert tool_results[0].tool_call_id == "call_1"
        assert tool_results[0].is_error is False

    @pytest.mark.asyncio
    async def test_output_truncation(self, registry, permissions):
        """Test that long output is truncated."""
        # Add tool that returns long output
        long_output = "x" * 200000

        registry.register(
            Tool(
                definition=ToolDefinition(
                    name="long_output",
                    description="Returns long output",
                    parameters=[],
                ),
                handler=lambda args: long_output,
                permission_level=PermissionLevel.SAFE,
            )
        )

        executor = ToolExecutor(
            registry=registry,
            permissions=permissions,
            max_output_length=1000,
        )

        tool_call = ToolCall(id="call_123", name="long_output", arguments={})

        result = await executor.execute(tool_call)

        assert result.success is True
        assert len(result.result) < 2000  # Truncated
        assert "truncated" in result.result
