"""Tests for the tool registry."""

import pytest

from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool, ToolRegistry, create_tool


class TestToolCreation:
    """Tests for creating Tool instances."""

    def test_create_simple_tool(self):
        """Test creating a basic tool."""
        definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="Argument 1"),
            ],
        )

        def handler(args):
            return f"Got: {args['arg1']}"

        tool = Tool(definition=definition, handler=handler)

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.permission_level == PermissionLevel.SAFE
        assert tool.category == "general"
        assert tool.timeout == 30.0
        assert tool.enabled is True

    def test_create_tool_with_all_options(self):
        """Test creating a tool with all options specified."""
        definition = ToolDefinition(
            name="dangerous_tool",
            description="A dangerous tool",
            parameters=[],
        )

        tool = Tool(
            definition=definition,
            handler=lambda args: "result",
            permission_level=PermissionLevel.DANGEROUS,
            description="Custom description",
            category="custom",
            timeout=60.0,
            enabled=False,
        )

        assert tool.name == "dangerous_tool"
        assert tool.description == "Custom description"
        assert tool.permission_level == PermissionLevel.DANGEROUS
        assert tool.category == "custom"
        assert tool.timeout == 60.0
        assert tool.enabled is False

    def test_create_tool_factory(self):
        """Test the create_tool factory function."""
        tool = create_tool(
            name="factory_tool",
            description="Created via factory",
            parameters=[
                ToolParameter(name="input", type="string", description="Input value"),
            ],
            handler=lambda args: args["input"].upper(),
            permission_level=PermissionLevel.CAUTIOUS,
            category="text",
            timeout=10.0,
        )

        assert tool.name == "factory_tool"
        assert tool.description == "Created via factory"
        assert tool.permission_level == PermissionLevel.CAUTIOUS
        assert tool.category == "text"


class TestToolRegistry:
    """Tests for the ToolRegistry class."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)

        assert registry.has("test_tool")
        assert len(registry) == 1

    def test_register_duplicate_raises(self):
        """Test that registering a duplicate tool raises."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool)

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)
        assert registry.has("test_tool")

        result = registry.unregister("test_tool")
        assert result is True
        assert not registry.has("test_tool")

    def test_unregister_nonexistent_returns_false(self):
        """Test unregistering a nonexistent tool returns False."""
        registry = ToolRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_tool(self):
        """Test getting a tool by name."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)

        retrieved = registry.get("test_tool")
        assert retrieved is tool

    def test_get_nonexistent_returns_none(self):
        """Test getting a nonexistent tool returns None."""
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_get_enabled_tool(self):
        """Test get_enabled returns enabled tools."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)

        assert registry.get_enabled("test_tool") is tool

    def test_get_enabled_disabled_tool_returns_none(self):
        """Test get_enabled returns None for disabled tools."""
        registry = ToolRegistry()

        tool = Tool(
            definition=ToolDefinition(name="test_tool", description="Test"),
            handler=lambda args: "result",
            enabled=False,
        )

        registry.register(tool)

        assert registry.get_enabled("test_tool") is None

    def test_enable_disable_tool(self):
        """Test enabling and disabling tools."""
        registry = ToolRegistry()

        tool = create_tool(
            name="test_tool",
            description="Test",
            parameters=[],
            handler=lambda args: "result",
        )

        registry.register(tool)

        registry.disable("test_tool")
        assert registry.get_enabled("test_tool") is None

        registry.enable("test_tool")
        assert registry.get_enabled("test_tool") is tool

    def test_list_tools(self):
        """Test listing tool names."""
        registry = ToolRegistry()

        for name in ["tool1", "tool2", "tool3"]:
            registry.register(
                create_tool(
                    name=name,
                    description=f"Tool {name}",
                    parameters=[],
                    handler=lambda args: "result",
                )
            )

        names = registry.list_tools()
        assert sorted(names) == ["tool1", "tool2", "tool3"]

    def test_list_tools_enabled_only(self):
        """Test listing only enabled tools."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="enabled_tool",
                description="Enabled",
                parameters=[],
                handler=lambda args: "result",
            )
        )
        registry.register(
            Tool(
                definition=ToolDefinition(name="disabled_tool", description="Disabled"),
                handler=lambda args: "result",
                enabled=False,
            )
        )

        enabled = registry.list_tools(enabled_only=True)
        assert enabled == ["enabled_tool"]

        all_tools = registry.list_tools(enabled_only=False)
        assert sorted(all_tools) == ["disabled_tool", "enabled_tool"]

    def test_list_by_category(self):
        """Test listing tools by category."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="file_tool",
                description="File tool",
                parameters=[],
                handler=lambda args: "result",
                category="file",
            )
        )
        registry.register(
            create_tool(
                name="shell_tool",
                description="Shell tool",
                parameters=[],
                handler=lambda args: "result",
                category="shell",
            )
        )

        file_tools = registry.list_by_category("file")
        assert file_tools == ["file_tool"]

        shell_tools = registry.list_by_category("shell")
        assert shell_tools == ["shell_tool"]

    def test_list_categories(self):
        """Test listing all categories."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="tool1",
                description="Tool 1",
                parameters=[],
                handler=lambda args: "result",
                category="file",
            )
        )
        registry.register(
            create_tool(
                name="tool2",
                description="Tool 2",
                parameters=[],
                handler=lambda args: "result",
                category="shell",
            )
        )

        categories = registry.list_categories()
        assert sorted(categories) == ["file", "shell"]

    def test_get_definitions(self):
        """Test getting tool definitions."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="tool1",
                description="Tool 1",
                parameters=[
                    ToolParameter(name="arg", type="string", description="Argument"),
                ],
                handler=lambda args: "result",
            )
        )

        definitions = registry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0].name == "tool1"

    def test_get_definitions_filtered_by_category(self):
        """Test getting definitions filtered by category."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="file_tool",
                description="File tool",
                parameters=[],
                handler=lambda args: "result",
                category="file",
            )
        )
        registry.register(
            create_tool(
                name="shell_tool",
                description="Shell tool",
                parameters=[],
                handler=lambda args: "result",
                category="shell",
            )
        )

        definitions = registry.get_definitions(categories=["file"])
        assert len(definitions) == 1
        assert definitions[0].name == "file_tool"

    def test_clear_registry(self):
        """Test clearing all tools from registry."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="tool1",
                description="Tool 1",
                parameters=[],
                handler=lambda args: "result",
            )
        )

        assert len(registry) == 1

        registry.clear()

        assert len(registry) == 0
        assert registry.list_tools() == []

    def test_contains(self):
        """Test the __contains__ method."""
        registry = ToolRegistry()

        registry.register(
            create_tool(
                name="test_tool",
                description="Test",
                parameters=[],
                handler=lambda args: "result",
            )
        )

        assert "test_tool" in registry
        assert "nonexistent" not in registry
