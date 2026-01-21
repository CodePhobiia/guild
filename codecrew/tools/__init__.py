"""Tool system for CodeCrew.

This package provides tool registration, execution, and permission management
for AI models to interact with the file system and shell.
"""

from codecrew.tools.registry import ToolRegistry, Tool, ToolHandler, create_tool
from codecrew.tools.executor import (
    ToolExecutor,
    ToolExecutionResult,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
)
from codecrew.tools.permissions import (
    PermissionManager,
    PermissionLevel,
    PermissionRequest,
    PermissionDeniedError,
)
from codecrew.tools.builtin import register_builtin_tools, get_builtin_tools

__all__ = [
    # Registry
    "ToolRegistry",
    "Tool",
    "ToolHandler",
    "create_tool",
    # Executor
    "ToolExecutor",
    "ToolExecutionResult",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolTimeoutError",
    "ToolValidationError",
    # Permissions
    "PermissionManager",
    "PermissionLevel",
    "PermissionRequest",
    "PermissionDeniedError",
    # Builtin tools
    "register_builtin_tools",
    "get_builtin_tools",
]
