"""Built-in tools for CodeCrew.

This package contains the default tools available to AI models:
- File operations (read, write, edit, list, search)
- Shell command execution
- Git operations (status, diff, log, branch, commit, etc.)

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
from codecrew.tools.builtin.git import (
    create_git_status_tool,
    create_git_diff_tool,
    create_git_log_tool,
    create_git_show_tool,
    create_git_branch_tool,
    create_git_checkout_tool,
    create_git_add_tool,
    create_git_commit_tool,
    create_git_stash_tool,
    create_git_blame_tool,
    get_git_tools,
    register_git_tools,
)
from codecrew.tools.registry import Tool, ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    include_git: bool = True,
) -> None:
    """Register all built-in tools with a registry.

    Args:
        registry: The tool registry to register with.
        working_directory: Base working directory for file operations.
                          If None, uses current directory.
        allowed_paths: List of paths that tools are allowed to access.
                      If None, no path restrictions are enforced.
        include_git: If True, include git tools (default: True).
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

    # Git tools
    if include_git:
        register_git_tools(
            registry=registry,
            working_directory=working_directory,
        )


def get_builtin_tools(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    include_git: bool = True,
) -> list[Tool]:
    """Get all built-in tools as a list.

    Args:
        working_directory: Base working directory for file operations.
        allowed_paths: List of paths that tools are allowed to access.
        include_git: If True, include git tools (default: True).

    Returns:
        List of Tool instances.
    """
    tools = [
        create_read_file_tool(working_directory, allowed_paths),
        create_write_file_tool(working_directory, allowed_paths),
        create_edit_file_tool(working_directory, allowed_paths),
        create_list_directory_tool(working_directory, allowed_paths),
        create_search_files_tool(working_directory, allowed_paths),
        create_execute_command_tool(working_directory),
    ]

    if include_git:
        tools.extend(get_git_tools(working_directory))

    return tools


__all__ = [
    "register_builtin_tools",
    "get_builtin_tools",
    # File tool factories
    "create_read_file_tool",
    "create_write_file_tool",
    "create_edit_file_tool",
    "create_list_directory_tool",
    "create_search_files_tool",
    # Shell tool factory
    "create_execute_command_tool",
    # Git tool factories
    "create_git_status_tool",
    "create_git_diff_tool",
    "create_git_log_tool",
    "create_git_show_tool",
    "create_git_branch_tool",
    "create_git_checkout_tool",
    "create_git_add_tool",
    "create_git_commit_tool",
    "create_git_stash_tool",
    "create_git_blame_tool",
    "get_git_tools",
    "register_git_tools",
]
