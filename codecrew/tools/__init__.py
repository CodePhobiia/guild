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
from codecrew.tools.context import (
    ToolContext,
    FileModification,
    FileReadRecord,
    compute_content_hash,
)

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
    # Context tracking
    "ToolContext",
    "FileModification",
    "FileReadRecord",
    "compute_content_hash",
    # Builtin tools
    "register_builtin_tools",
    "get_builtin_tools",
]
