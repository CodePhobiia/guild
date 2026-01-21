"""Tests for tool definitions."""

import pytest

from codecrew.models.tools import (
    DEFAULT_TOOLS,
    ToolDefinition,
    ToolParameter,
    tools_to_anthropic,
    tools_to_google,
    tools_to_openai,
    tools_to_xai,
)


class TestToolParameter:
    """Tests for ToolParameter class."""

    def test_create_parameter(self) -> None:
        """Test creating a tool parameter."""
        param = ToolParameter(
            name="path",
            type="string",
            description="The file path",
            required=True,
        )
        assert param.name == "path"
        assert param.type == "string"
        assert param.description == "The file path"
        assert param.required is True

    def test_to_json_schema_simple(self) -> None:
        """Test converting parameter to JSON schema."""
        param = ToolParameter(
            name="count",
            type="integer",
            description="Number of items",
        )
        schema = param.to_json_schema()

        assert schema["type"] == "integer"
        assert schema["description"] == "Number of items"

    def test_to_json_schema_with_enum(self) -> None:
        """Test converting parameter with enum to JSON schema."""
        param = ToolParameter(
            name="format",
            type="string",
            description="Output format",
            enum=["json", "yaml", "toml"],
        )
        schema = param.to_json_schema()

        assert schema["enum"] == ["json", "yaml", "toml"]


class TestToolDefinition:
    """Tests for ToolDefinition class."""

    def test_create_tool(self) -> None:
        """Test creating a tool definition."""
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            parameters=[
                ToolParameter(name="path", type="string", description="File path"),
            ],
        )
        assert tool.name == "read_file"
        assert len(tool.parameters) == 1

    def test_to_anthropic(self) -> None:
        """Test converting to Anthropic format."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="First arg"),
                ToolParameter(name="arg2", type="integer", description="Second arg", required=False),
            ],
        )
        anthropic = tool.to_anthropic()

        assert anthropic["name"] == "test_tool"
        assert anthropic["description"] == "A test tool"
        assert "input_schema" in anthropic
        assert anthropic["input_schema"]["type"] == "object"
        assert "arg1" in anthropic["input_schema"]["properties"]
        assert "arg2" in anthropic["input_schema"]["properties"]
        assert "arg1" in anthropic["input_schema"]["required"]
        assert "arg2" not in anthropic["input_schema"]["required"]

    def test_to_openai(self) -> None:
        """Test converting to OpenAI format."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="path", type="string", description="Path"),
            ],
        )
        openai = tool.to_openai()

        assert openai["type"] == "function"
        assert openai["function"]["name"] == "test_tool"
        assert openai["function"]["description"] == "A test tool"
        assert "parameters" in openai["function"]

    def test_to_google(self) -> None:
        """Test converting to Google format."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query"),
            ],
        )
        google = tool.to_google()

        assert google["name"] == "test_tool"
        assert google["description"] == "A test tool"
        assert "parameters" in google

    def test_to_xai(self) -> None:
        """Test converting to xAI format (should match OpenAI)."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[],
        )
        xai = tool.to_xai()
        openai = tool.to_openai()

        assert xai == openai


class TestToolConversionFunctions:
    """Tests for batch tool conversion functions."""

    def test_tools_to_anthropic(self) -> None:
        """Test converting multiple tools to Anthropic format."""
        tools = [
            ToolDefinition(name="tool1", description="Tool 1", parameters=[]),
            ToolDefinition(name="tool2", description="Tool 2", parameters=[]),
        ]
        result = tools_to_anthropic(tools)

        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"

    def test_tools_to_openai(self) -> None:
        """Test converting multiple tools to OpenAI format."""
        tools = [
            ToolDefinition(name="tool1", description="Tool 1", parameters=[]),
        ]
        result = tools_to_openai(tools)

        assert len(result) == 1
        assert result[0]["type"] == "function"

    def test_tools_to_google(self) -> None:
        """Test converting multiple tools to Google format."""
        tools = [
            ToolDefinition(name="tool1", description="Tool 1", parameters=[]),
        ]
        result = tools_to_google(tools)

        assert len(result) == 1
        assert result[0]["name"] == "tool1"

    def test_tools_to_xai(self) -> None:
        """Test converting multiple tools to xAI format."""
        tools = [
            ToolDefinition(name="tool1", description="Tool 1", parameters=[]),
        ]
        result = tools_to_xai(tools)

        assert len(result) == 1
        assert result[0]["type"] == "function"


class TestDefaultTools:
    """Tests for default tool definitions."""

    def test_default_tools_exist(self) -> None:
        """Test that default tools are defined."""
        assert len(DEFAULT_TOOLS) > 0

    def test_read_file_tool(self) -> None:
        """Test read_file tool definition."""
        read_file = next((t for t in DEFAULT_TOOLS if t.name == "read_file"), None)
        assert read_file is not None
        assert "path" in [p.name for p in read_file.parameters]

    def test_write_file_tool(self) -> None:
        """Test write_file tool definition."""
        write_file = next((t for t in DEFAULT_TOOLS if t.name == "write_file"), None)
        assert write_file is not None
        assert "path" in [p.name for p in write_file.parameters]
        assert "content" in [p.name for p in write_file.parameters]

    def test_execute_command_tool(self) -> None:
        """Test execute_command tool definition."""
        exec_cmd = next((t for t in DEFAULT_TOOLS if t.name == "execute_command"), None)
        assert exec_cmd is not None
        assert "command" in [p.name for p in exec_cmd.parameters]

    def test_all_default_tools_convert(self) -> None:
        """Test that all default tools can be converted to all formats."""
        for tool in DEFAULT_TOOLS:
            # Should not raise
            anthropic = tool.to_anthropic()
            openai = tool.to_openai()
            google = tool.to_google()
            xai = tool.to_xai()

            assert anthropic["name"] == tool.name
            assert openai["function"]["name"] == tool.name
            assert google["name"] == tool.name
            assert xai["function"]["name"] == tool.name
