"""Built-in tools for CodeCrew.

This package contains the default tools available to AI models:
- File operations (read, write, edit, list, search)
- Shell command execution

All tools are registered with appropriate permission levels.
"""

from codecrew.tools.builtin.files import (
    create_read_file_tool,
    create_write_file_tool,
    create_edit_file_tool,
    create_list_directory_tool,
    create_search_files_tool,
)
from codecrew.tools.builtin.shell import create_execute_command_tool
from codecrew.tools.registry import Tool, ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
) -> None:
    """Register all built-in tools with a registry.

    Args:
        registry: The tool registry to register with.
        working_directory: Base working directory for file operations.
                          If None, uses current directory.
        allowed_paths: List of paths that tools are allowed to access.
                      If None, no path restrictions are enforced.
    """
    # File tools
    registry.register(
        create_read_file_tool(
            working_directory=working_directory,
            allowed_paths=allowed_paths,
        )
    )
    registry.register(
        create_write_file_tool(
            working_directory=working_directory,
            allowed_paths=allowed_paths,
        )
    )
    registry.register(
        create_edit_file_tool(
            working_directory=working_directory,
            allowed_paths=allowed_paths,
        )
    )
    registry.register(
        create_list_directory_tool(
            working_directory=working_directory,
            allowed_paths=allowed_paths,
        )
    )
    registry.register(
        create_search_files_tool(
            working_directory=working_directory,
            allowed_paths=allowed_paths,
        )
    )

    # Shell tool
    registry.register(
        create_execute_command_tool(
            working_directory=working_directory,
        )
    )


def get_builtin_tools(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
) -> list[Tool]:
    """Get all built-in tools as a list.

    Args:
        working_directory: Base working directory for file operations.
        allowed_paths: List of paths that tools are allowed to access.

    Returns:
        List of Tool instances.
    """
    return [
        create_read_file_tool(working_directory, allowed_paths),
        create_write_file_tool(working_directory, allowed_paths),
        create_edit_file_tool(working_directory, allowed_paths),
        create_list_directory_tool(working_directory, allowed_paths),
        create_search_files_tool(working_directory, allowed_paths),
        create_execute_command_tool(working_directory),
    ]


__all__ = [
    "register_builtin_tools",
    "get_builtin_tools",
    # Individual tool factories
    "create_read_file_tool",
    "create_write_file_tool",
    "create_edit_file_tool",
    "create_list_directory_tool",
    "create_search_files_tool",
    "create_execute_command_tool",
]
