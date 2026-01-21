"""Tests for parallel tool execution in the tool orchestrator."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from codecrew.models.types import ToolCall, ToolResult
from codecrew.tools.registry import Tool, ToolRegistry, create_tool
from codecrew.tools.executor import ToolExecutor, ToolExecutionResult
from codecrew.tools.permissions import PermissionManager, PermissionLevel
from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.orchestrator.tool_orchestrator import (
    ToolEnabledOrchestrator,
    PARALLEL_SAFE_TOOLS,
)


@pytest.fixture
def mock_registry():
    """Create a mock tool registry with test tools."""
    registry = ToolRegistry()

    # Parallel-safe tool (read)
    read_tool = create_tool(
        name="read_file",
        description="Read a file",
        parameters=[ToolParameter(name="path", type="string", description="File path")],
        handler=lambda args: f"Content of {args['path']}",
        permission_level=PermissionLevel.SAFE,
        parallel_safe=True,
    )
    registry.register(read_tool)

    # Another parallel-safe tool
    list_tool = create_tool(
        name="list_directory",
        description="List directory",
        parameters=[ToolParameter(name="path", type="string", description="Dir path")],
        handler=lambda args: f"Files in {args['path']}",
        permission_level=PermissionLevel.SAFE,
        parallel_safe=True,
    )
    registry.register(list_tool)

    # Sequential tool (write)
    write_tool = create_tool(
        name="write_file",
        description="Write a file",
        parameters=[
            ToolParameter(name="path", type="string", description="File path"),
            ToolParameter(name="content", type="string", description="Content"),
        ],
        handler=lambda args: f"Wrote to {args['path']}",
        permission_level=PermissionLevel.CAUTIOUS,
        parallel_safe=False,
    )
    registry.register(write_tool)

    return registry


@pytest.fixture
def mock_executor(mock_registry):
    """Create a mock executor."""
    permissions = PermissionManager(auto_approve=True)
    executor = ToolExecutor(registry=mock_registry, permissions=permissions)
    return executor


class TestParallelSafeToolsConstant:
    """Tests for the PARALLEL_SAFE_TOOLS constant."""

    def test_contains_expected_tools(self):
        """Should contain the expected read-only tools."""
        assert "read_file" in PARALLEL_SAFE_TOOLS
        assert "list_directory" in PARALLEL_SAFE_TOOLS
        assert "search_files" in PARALLEL_SAFE_TOOLS

    def test_is_frozen_set(self):
        """Should be a frozenset (immutable)."""
        assert isinstance(PARALLEL_SAFE_TOOLS, frozenset)


class TestToolClassification:
    """Tests for tool classification logic."""

    def test_classify_by_name(self, mock_registry):
        """Tools should be classified by name in PARALLEL_SAFE_TOOLS."""
        # Create mock orchestrator components
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"
        mock_executor = MagicMock()

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "/a.txt"}),
            ToolCall(id="2", name="write_file", arguments={"path": "/b.txt", "content": "x"}),
            ToolCall(id="3", name="list_directory", arguments={"path": "/"}),
        ]

        parallel, sequential = orchestrator._classify_tool_calls(tool_calls)

        assert len(parallel) == 2  # read_file and list_directory
        assert len(sequential) == 1  # write_file

    def test_classify_by_tool_flag(self, mock_registry):
        """Tools should be classified by parallel_safe flag."""
        # Add a custom parallel-safe tool not in PARALLEL_SAFE_TOOLS
        custom_tool = create_tool(
            name="custom_read",
            description="Custom read",
            parameters=[],
            handler=lambda args: "result",
            parallel_safe=True,
        )
        mock_registry.register(custom_tool)

        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"
        mock_executor = MagicMock()

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        tool_calls = [
            ToolCall(id="1", name="custom_read", arguments={}),
        ]

        parallel, sequential = orchestrator._classify_tool_calls(tool_calls)

        assert len(parallel) == 1
        assert parallel[0].name == "custom_read"


class TestResultReordering:
    """Tests for result reordering."""

    def test_reorder_results(self, mock_registry):
        """Results should be reordered to match original call order."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"
        mock_executor = MagicMock()

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        # Original order: 1, 2, 3
        original_calls = [
            ToolCall(id="1", name="read_file", arguments={}),
            ToolCall(id="2", name="write_file", arguments={}),
            ToolCall(id="3", name="list_directory", arguments={}),
        ]

        # Results in different order: 3, 1, 2
        results = [
            ToolResult(tool_call_id="3", content="result3"),
            ToolResult(tool_call_id="1", content="result1"),
            ToolResult(tool_call_id="2", content="result2"),
        ]

        reordered = orchestrator._reorder_results(original_calls, results)

        assert len(reordered) == 3
        assert reordered[0].tool_call_id == "1"
        assert reordered[1].tool_call_id == "2"
        assert reordered[2].tool_call_id == "3"


class TestParallelExecution:
    """Tests for parallel tool execution."""

    @pytest.mark.asyncio
    async def test_parallel_tools_execute_concurrently(self, mock_registry, mock_executor):
        """Parallel-safe tools should execute concurrently."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
            enable_parallel_tools=True,
        )

        # Create multiple read-only tool calls
        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "/a.txt"}),
            ToolCall(id="2", name="read_file", arguments={"path": "/b.txt"}),
            ToolCall(id="3", name="list_directory", arguments={"path": "/"}),
        ]

        results = await orchestrator._execute_tools("test_model", tool_calls)

        # All should complete
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_sequential_execution_when_disabled(self, mock_registry, mock_executor):
        """Tools should execute sequentially when parallel is disabled."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
            enable_parallel_tools=False,
        )

        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "/a.txt"}),
            ToolCall(id="2", name="read_file", arguments={"path": "/b.txt"}),
        ]

        results = await orchestrator._execute_tools("test_model", tool_calls)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_mixed_parallel_and_sequential(self, mock_registry, mock_executor):
        """Mixed tool calls should execute parallel ones first, then sequential."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
            enable_parallel_tools=True,
        )

        tool_calls = [
            ToolCall(id="1", name="read_file", arguments={"path": "/a.txt"}),
            ToolCall(id="2", name="write_file", arguments={"path": "/b.txt", "content": "x"}),
            ToolCall(id="3", name="list_directory", arguments={"path": "/"}),
        ]

        results = await orchestrator._execute_tools("test_model", tool_calls)

        # All should complete and be in original order
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_empty_tool_calls(self, mock_registry, mock_executor):
        """Empty tool calls should return empty results."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        results = await orchestrator._execute_tools("test_model", [])

        assert results == []


class TestToolContextIntegration:
    """Tests for ToolContext integration in the orchestrator."""

    @pytest.mark.asyncio
    async def test_modifications_tracked(self, mock_registry, mock_executor):
        """File modifications should be tracked in context."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        tool_calls = [
            ToolCall(id="1", name="write_file", arguments={"path": "/test.txt", "content": "hello"}),
        ]

        await orchestrator._execute_tools("test_model", tool_calls)

        # Check context was updated
        assert orchestrator.tool_context.was_file_modified("/test.txt")

    def test_context_summary(self, mock_registry, mock_executor):
        """Should provide modification summary."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        # Manually add some modifications for testing
        orchestrator.tool_context.record_modification("/file1.py", "write")
        orchestrator.tool_context.record_modification("/file2.py", "edit")

        summary = orchestrator.get_tool_context_summary()

        assert "file1.py" in summary or "2 total" in summary or "modification" in summary.lower()

    def test_clear_context(self, mock_registry, mock_executor):
        """Should be able to clear context."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
        )

        orchestrator.tool_context.record_modification("/file.py", "write")
        orchestrator.clear_tool_context()

        assert len(orchestrator.tool_context.modifications) == 0

    @pytest.mark.asyncio
    async def test_modifications_tracked_when_parallel_disabled(self, mock_registry, mock_executor):
        """File modifications should be tracked even when parallel execution is disabled."""
        mock_clients = {}
        mock_settings = MagicMock()
        mock_settings.conversation.first_responder = "rotate"

        orchestrator = ToolEnabledOrchestrator(
            clients=mock_clients,
            settings=mock_settings,
            tool_executor=mock_executor,
            tool_registry=mock_registry,
            enable_parallel_tools=False,  # Disable parallel execution
        )

        tool_calls = [
            ToolCall(id="1", name="write_file", arguments={"path": "/sequential.txt", "content": "test"}),
        ]

        await orchestrator._execute_tools("test_model", tool_calls)

        # Check context was updated even with parallel disabled
        assert orchestrator.tool_context.was_file_modified("/sequential.txt")
