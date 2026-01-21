"""End-to-end tests for tool system workflows.

These tests verify the tool system components work correctly
without deep mocking of the orchestrator internals.
"""

import pytest
from pathlib import Path

from codecrew.models.types import ToolCall
from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.tools import (
    ToolRegistry,
    ToolExecutor,
    PermissionManager,
    register_builtin_tools,
    create_tool,
)
from codecrew.tools.permissions import PermissionLevel


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def test_builtin_tools_registered(self):
        """Test that built-in tools are registered."""
        registry = ToolRegistry()
        register_builtin_tools(registry)

        tool_names = registry.list_tools()
        assert len(tool_names) > 0
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names

    def test_custom_tool_registration(self):
        """Test registering a custom tool."""
        registry = ToolRegistry()

        custom_tool = create_tool(
            name="custom_test",
            description="A custom test tool",
            parameters=[
                ToolParameter(name="input", type="string", description="Input value"),
            ],
            handler=lambda args: f"Processed: {args['input']}",
            permission_level=PermissionLevel.SAFE,
        )

        registry.register(custom_tool)

        assert "custom_test" in registry.list_tools()
        assert registry.get("custom_test") is not None

    def test_get_tool_definitions(self):
        """Test getting tool definitions for model consumption."""
        registry = ToolRegistry()
        register_builtin_tools(registry)

        definitions = registry.get_definitions()
        assert len(definitions) > 0
        assert all(isinstance(d, ToolDefinition) for d in definitions)

    def test_tool_enable_disable(self):
        """Test enabling and disabling tools."""
        registry = ToolRegistry()

        tool = create_tool(
            name="toggle_test",
            description="Test tool",
            parameters=[],
            handler=lambda args: "ok",
        )
        registry.register(tool)

        # Should be enabled by default
        assert "toggle_test" in registry.list_tools(enabled_only=True)

        # Disable
        registry.disable("toggle_test")
        assert "toggle_test" not in registry.list_tools(enabled_only=True)
        assert "toggle_test" in registry.list_tools(enabled_only=False)

        # Re-enable
        registry.enable("toggle_test")
        assert "toggle_test" in registry.list_tools(enabled_only=True)


class TestPermissionManager:
    """Tests for permission management."""

    def test_auto_approve_mode(self):
        """Test auto-approve mode."""
        pm = PermissionManager(auto_approve=True)

        # Auto-approve should grant permission regardless of level
        assert pm.check_permission(
            tool_name="write_file",
            arguments={"path": "/test"},
            permission_level=PermissionLevel.CAUTIOUS,
        )

    def test_permission_levels(self):
        """Test permission level hierarchy."""
        assert PermissionLevel.SAFE < PermissionLevel.CAUTIOUS
        assert PermissionLevel.CAUTIOUS < PermissionLevel.DANGEROUS
        assert PermissionLevel.DANGEROUS < PermissionLevel.BLOCKED

    def test_session_grants(self):
        """Test session-level permission grants."""
        pm = PermissionManager(auto_approve=False)

        # Grant permission for a tool
        pm.grant_session_permission("test_tool")

        # Should have session permission
        assert pm.has_session_permission("test_tool")
        assert pm.check_permission(
            tool_name="test_tool",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
        )

    def test_blocked_permission(self):
        """Test blocked permission level."""
        pm = PermissionManager(auto_approve=True)

        # Block a tool
        pm.block_tool("dangerous_tool")

        # Even auto-approve should not approve BLOCKED tools
        with pytest.raises(Exception):  # PermissionDeniedError
            pm.check_permission(
                tool_name="dangerous_tool",
                arguments={},
                permission_level=PermissionLevel.DANGEROUS,
            )


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.fixture
    def executor(self):
        """Create a tool executor with built-in tools."""
        registry = ToolRegistry()
        register_builtin_tools(registry)
        permissions = PermissionManager(auto_approve=True)
        return ToolExecutor(registry=registry, permissions=permissions)

    @pytest.mark.asyncio
    async def test_read_file(self, executor, tmp_path):
        """Test reading a file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # Grant path permission
        executor.permissions.set_tool_permission("read_file", PermissionLevel.SAFE)

        tool_call = ToolCall(
            id="test_read_1",
            name="read_file",
            arguments={"path": str(test_file)},
        )

        result = await executor.execute(tool_call)

        assert result.success
        assert "Hello, World!" in result.result

    @pytest.mark.asyncio
    async def test_write_file(self, executor, tmp_path):
        """Test writing a file."""
        test_file = tmp_path / "output.txt"

        tool_call = ToolCall(
            id="test_write_1",
            name="write_file",
            arguments={"path": str(test_file), "content": "Test content"},
        )

        result = await executor.execute(tool_call)

        assert result.success
        assert test_file.exists()
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_list_directory(self, executor, tmp_path):
        """Test listing directory contents."""
        # Create some files
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        (tmp_path / "subdir").mkdir()

        tool_call = ToolCall(
            id="test_list_1",
            name="list_directory",
            arguments={"path": str(tmp_path)},
        )

        result = await executor.execute(tool_call)

        assert result.success
        assert "file1.txt" in result.result
        assert "file2.txt" in result.result

    @pytest.mark.asyncio
    async def test_custom_tool_execution(self, tmp_path):
        """Test executing a custom tool."""
        registry = ToolRegistry()

        def custom_handler(args):
            return f"Result: {args['value'] * 2}"

        tool = create_tool(
            name="double",
            description="Doubles a number",
            parameters=[
                ToolParameter(name="value", type="integer", description="Number to double"),
            ],
            handler=custom_handler,
        )
        registry.register(tool)

        permissions = PermissionManager(auto_approve=True)
        executor = ToolExecutor(registry=registry, permissions=permissions)

        tool_call = ToolCall(
            id="test_double_1",
            name="double",
            arguments={"value": 21},
        )

        result = await executor.execute(tool_call)

        assert result.success
        assert "42" in result.result


class TestToolDefinitions:
    """Tests for tool definition structures."""

    def test_tool_definition_creation(self):
        """Test creating a tool definition."""
        definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="First argument"),
                ToolParameter(name="arg2", type="integer", description="Second argument", required=False),
            ],
        )

        assert definition.name == "test_tool"
        assert len(definition.parameters) == 2
        assert definition.parameters[0].required  # Default is True
        assert not definition.parameters[1].required

    def test_tool_parameter_types(self):
        """Test different parameter types."""
        params = [
            ToolParameter(name="str_arg", type="string", description="String"),
            ToolParameter(name="int_arg", type="integer", description="Integer"),
            ToolParameter(name="bool_arg", type="boolean", description="Boolean"),
            ToolParameter(name="num_arg", type="number", description="Number"),
        ]

        for param in params:
            assert param.type in ["string", "integer", "boolean", "number", "array", "object"]


class TestToolCall:
    """Tests for tool call structures."""

    def test_tool_call_creation(self):
        """Test creating a tool call."""
        call = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "/test/file.txt"},
        )

        assert call.id == "call_123"
        assert call.name == "read_file"
        assert call.arguments["path"] == "/test/file.txt"

    def test_tool_call_with_complex_arguments(self):
        """Test tool call with complex arguments."""
        call = ToolCall(
            id="call_456",
            name="search_files",
            arguments={
                "pattern": "*.py",
                "directory": "/src",
                "recursive": True,
                "max_results": 100,
            },
        )

        assert call.arguments["recursive"] is True
        assert call.arguments["max_results"] == 100
