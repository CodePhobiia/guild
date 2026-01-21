"""Tool definitions with provider-specific translations."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolParameter:
    """A parameter for a tool."""

    name: str
    type: str  # 'string', 'integer', 'number', 'boolean', 'array', 'object'
    description: str
    required: bool = True
    enum: Optional[list[str]] = None
    items: Optional[dict[str, Any]] = None  # For array types
    properties: Optional[dict[str, Any]] = None  # For object types

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format."""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.items:
            schema["items"] = self.items
        if self.properties:
            schema["properties"] = self.properties
        return schema


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by models."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def _build_json_schema(self) -> dict[str, Any]:
        """Build JSON schema for parameters."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return schema

    def to_anthropic(self) -> dict[str, Any]:
        """Convert to Anthropic tool format.

        Anthropic format:
        {
            "name": "tool_name",
            "description": "tool description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._build_json_schema(),
        }

    def to_openai(self) -> dict[str, Any]:
        """Convert to OpenAI function/tool format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "tool description",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._build_json_schema(),
            },
        }

    def to_google(self) -> dict[str, Any]:
        """Convert to Google Gemini function declaration format.

        Google format:
        {
            "name": "tool_name",
            "description": "tool description",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._build_json_schema(),
        }

    def to_xai(self) -> dict[str, Any]:
        """Convert to xAI/Grok format (OpenAI-compatible)."""
        return self.to_openai()


def tools_to_anthropic(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert a list of tools to Anthropic format."""
    return [tool.to_anthropic() for tool in tools]


def tools_to_openai(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert a list of tools to OpenAI format."""
    return [tool.to_openai() for tool in tools]


def tools_to_google(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert a list of tools to Google format."""
    return [tool.to_google() for tool in tools]


def tools_to_xai(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Convert a list of tools to xAI format."""
    return [tool.to_xai() for tool in tools]


# Pre-defined tools for CodeCrew
READ_FILE_TOOL = ToolDefinition(
    name="read_file",
    description="Read the contents of a file at the specified path",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The path to the file to read",
        ),
    ],
)

WRITE_FILE_TOOL = ToolDefinition(
    name="write_file",
    description="Write content to a file at the specified path",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The path to the file to write",
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The content to write to the file",
        ),
    ],
)

EDIT_FILE_TOOL = ToolDefinition(
    name="edit_file",
    description="Make targeted edits to a file",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The path to the file to edit",
        ),
        ToolParameter(
            name="edits",
            type="array",
            description="List of edits to make",
            items={
                "type": "object",
                "properties": {
                    "old_text": {"type": "string", "description": "Text to find"},
                    "new_text": {"type": "string", "description": "Text to replace with"},
                },
                "required": ["old_text", "new_text"],
            },
        ),
    ],
)

EXECUTE_COMMAND_TOOL = ToolDefinition(
    name="execute_command",
    description="Execute a shell command",
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="The command to execute",
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Working directory for the command",
            required=False,
        ),
    ],
)

SEARCH_FILES_TOOL = ToolDefinition(
    name="search_files",
    description="Search for a pattern in files",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="The pattern to search for (regex supported)",
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Directory to search in",
            required=False,
        ),
        ToolParameter(
            name="file_pattern",
            type="string",
            description="Glob pattern to filter files (e.g., '*.py')",
            required=False,
        ),
    ],
)

LIST_DIRECTORY_TOOL = ToolDefinition(
    name="list_directory",
    description="List files and directories at a path",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The directory path to list",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to list recursively",
            required=False,
        ),
    ],
)

# Git tools
GIT_STATUS_TOOL = ToolDefinition(
    name="git_status",
    description="Get the current git repository status including branch, staged/unstaged changes, and untracked files",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the repository (optional, uses current directory)",
            required=False,
        ),
    ],
)

GIT_DIFF_TOOL = ToolDefinition(
    name="git_diff",
    description="Show changes between commits, commit and working tree, etc.",
    parameters=[
        ToolParameter(
            name="staged",
            type="boolean",
            description="Show staged changes instead of unstaged",
            required=False,
        ),
        ToolParameter(
            name="file",
            type="string",
            description="Specific file to diff",
            required=False,
        ),
        ToolParameter(
            name="commit",
            type="string",
            description="Compare with specific commit (e.g., HEAD~1, abc123)",
            required=False,
        ),
    ],
)

GIT_LOG_TOOL = ToolDefinition(
    name="git_log",
    description="Show commit history",
    parameters=[
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of commits to show (default: 10)",
            required=False,
        ),
        ToolParameter(
            name="file",
            type="string",
            description="Show history for specific file",
            required=False,
        ),
        ToolParameter(
            name="author",
            type="string",
            description="Filter by author",
            required=False,
        ),
        ToolParameter(
            name="since",
            type="string",
            description="Show commits since date (e.g., '2024-01-01', '1 week ago')",
            required=False,
        ),
    ],
)

GIT_SHOW_TOOL = ToolDefinition(
    name="git_show",
    description="Show details of a specific commit",
    parameters=[
        ToolParameter(
            name="commit",
            type="string",
            description="Commit hash or reference (e.g., HEAD, abc123, main~2)",
            required=False,
        ),
        ToolParameter(
            name="stat",
            type="boolean",
            description="Show diffstat instead of full diff",
            required=False,
        ),
    ],
)

GIT_BRANCH_TOOL = ToolDefinition(
    name="git_branch",
    description="List, create, or delete branches",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform",
            enum=["list", "create", "delete", "current"],
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Branch name (for create/delete)",
            required=False,
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Include remote branches (for list)",
            required=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force delete even if not merged",
            required=False,
        ),
    ],
)

GIT_CHECKOUT_TOOL = ToolDefinition(
    name="git_checkout",
    description="Switch branches or restore working tree files",
    parameters=[
        ToolParameter(
            name="target",
            type="string",
            description="Branch name or commit to checkout",
        ),
        ToolParameter(
            name="create",
            type="boolean",
            description="Create branch if it doesn't exist (-b flag)",
            required=False,
        ),
    ],
)

GIT_ADD_TOOL = ToolDefinition(
    name="git_add",
    description="Add file contents to the staging area",
    parameters=[
        ToolParameter(
            name="files",
            type="array",
            description="Files to add (use ['.'] for all)",
            items={"type": "string"},
        ),
    ],
)

GIT_COMMIT_TOOL = ToolDefinition(
    name="git_commit",
    description="Record changes to the repository",
    parameters=[
        ToolParameter(
            name="message",
            type="string",
            description="Commit message",
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Automatically stage modified/deleted files (-a flag)",
            required=False,
        ),
    ],
)

GIT_STASH_TOOL = ToolDefinition(
    name="git_stash",
    description="Stash changes in working directory",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Stash action",
            enum=["push", "pop", "list", "show", "drop"],
        ),
        ToolParameter(
            name="message",
            type="string",
            description="Message for stash push",
            required=False,
        ),
        ToolParameter(
            name="index",
            type="integer",
            description="Stash index for pop/show/drop (default: 0)",
            required=False,
        ),
    ],
)

GIT_BLAME_TOOL = ToolDefinition(
    name="git_blame",
    description="Show what revision and author last modified each line of a file",
    parameters=[
        ToolParameter(
            name="file",
            type="string",
            description="File to blame",
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Starting line number",
            required=False,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Ending line number",
            required=False,
        ),
    ],
)

# All default tools
DEFAULT_TOOLS = [
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
    EDIT_FILE_TOOL,
    EXECUTE_COMMAND_TOOL,
    SEARCH_FILES_TOOL,
    LIST_DIRECTORY_TOOL,
]

# Git tools (separate list for optional registration)
GIT_TOOLS = [
    GIT_STATUS_TOOL,
    GIT_DIFF_TOOL,
    GIT_LOG_TOOL,
    GIT_SHOW_TOOL,
    GIT_BRANCH_TOOL,
    GIT_CHECKOUT_TOOL,
    GIT_ADD_TOOL,
    GIT_COMMIT_TOOL,
    GIT_STASH_TOOL,
    GIT_BLAME_TOOL,
]
