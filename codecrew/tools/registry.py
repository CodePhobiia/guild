"""Tool registry for managing and discovering tools.

The registry provides a central place to register tools with their handlers
and metadata, enabling the orchestrator to discover available tools and
route tool calls to the appropriate handlers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional, Union

from codecrew.models.tools import ToolDefinition, ToolParameter
from codecrew.tools.permissions import PermissionLevel

logger = logging.getLogger(__name__)

# Type alias for tool handler functions
# Handlers can be sync or async, taking a dict of arguments and returning any result
ToolHandler = Union[
    Callable[[dict[str, Any]], Any],
    Callable[[dict[str, Any]], Coroutine[Any, Any, Any]],
]


@dataclass
class Tool:
    """A registered tool with its definition and handler.

    Attributes:
        definition: The tool's schema definition for model consumption.
        handler: The function that executes the tool.
        permission_level: Required permission level for execution.
        description: Human-readable description for confirmation dialogs.
        category: Tool category for organization (e.g., "file", "shell").
        timeout: Maximum execution time in seconds (None = no timeout).
        enabled: Whether the tool is currently available.
    """

    definition: ToolDefinition
    handler: ToolHandler
    permission_level: PermissionLevel = PermissionLevel.SAFE
    description: str = ""
    category: str = "general"
    timeout: Optional[float] = 30.0
    enabled: bool = True

    @property
    def name(self) -> str:
        """Get the tool name from its definition."""
        return self.definition.name

    def __post_init__(self) -> None:
        """Set description from definition if not provided."""
        if not self.description:
            self.description = self.definition.description


@dataclass
class ToolRegistry:
    """Registry for managing available tools.

    The registry maintains a collection of tools that can be made available
    to AI models. It provides methods for registering, discovering, and
    retrieving tools by name or category.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(Tool(
        ...     definition=ToolDefinition(name="greet", description="Say hello"),
        ...     handler=lambda args: f"Hello, {args.get('name', 'World')}!",
        ... ))
        >>> tool = registry.get("greet")
        >>> definitions = registry.get_definitions()
    """

    _tools: dict[str, Tool] = field(default_factory=dict)
    _categories: dict[str, list[str]] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: The tool to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool

        # Track by category
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

        logger.debug(f"Registered tool: {tool.name} (category: {tool.category})")

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.

        Returns:
            True if the tool was removed, False if it wasn't registered.
        """
        if name not in self._tools:
            return False

        tool = self._tools.pop(name)

        # Remove from category tracking
        if tool.category in self._categories:
            self._categories[tool.category].remove(name)
            if not self._categories[tool.category]:
                del self._categories[tool.category]

        logger.debug(f"Unregistered tool: {name}")
        return True

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: The tool name.

        Returns:
            The tool if found, None otherwise.
        """
        return self._tools.get(name)

    def get_enabled(self, name: str) -> Optional[Tool]:
        """Get a tool by name, only if it's enabled.

        Args:
            name: The tool name.

        Returns:
            The tool if found and enabled, None otherwise.
        """
        tool = self._tools.get(name)
        if tool and tool.enabled:
            return tool
        return None

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: The tool name.

        Returns:
            True if the tool is registered.
        """
        return name in self._tools

    def enable(self, name: str) -> bool:
        """Enable a tool.

        Args:
            name: The tool name.

        Returns:
            True if the tool was enabled, False if not found.
        """
        tool = self._tools.get(name)
        if tool:
            tool.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool.

        Args:
            name: The tool name.

        Returns:
            True if the tool was disabled, False if not found.
        """
        tool = self._tools.get(name)
        if tool:
            tool.enabled = False
            return True
        return False

    def list_tools(self, enabled_only: bool = True) -> list[str]:
        """List all registered tool names.

        Args:
            enabled_only: If True, only return enabled tools.

        Returns:
            List of tool names.
        """
        if enabled_only:
            return [name for name, tool in self._tools.items() if tool.enabled]
        return list(self._tools.keys())

    def list_by_category(
        self, category: str, enabled_only: bool = True
    ) -> list[str]:
        """List tools in a specific category.

        Args:
            category: The category to filter by.
            enabled_only: If True, only return enabled tools.

        Returns:
            List of tool names in the category.
        """
        names = self._categories.get(category, [])
        if enabled_only:
            return [n for n in names if self._tools[n].enabled]
        return list(names)

    def list_categories(self) -> list[str]:
        """List all tool categories.

        Returns:
            List of category names.
        """
        return list(self._categories.keys())

    def get_definitions(
        self,
        enabled_only: bool = True,
        categories: Optional[list[str]] = None,
    ) -> list[ToolDefinition]:
        """Get tool definitions for model consumption.

        Args:
            enabled_only: If True, only return enabled tools.
            categories: If provided, filter by these categories.

        Returns:
            List of tool definitions.
        """
        definitions = []

        for name, tool in self._tools.items():
            if enabled_only and not tool.enabled:
                continue
            if categories and tool.category not in categories:
                continue
            definitions.append(tool.definition)

        return definitions

    def get_all_tools(self, enabled_only: bool = True) -> list[Tool]:
        """Get all registered tools.

        Args:
            enabled_only: If True, only return enabled tools.

        Returns:
            List of tools.
        """
        if enabled_only:
            return [t for t in self._tools.values() if t.enabled]
        return list(self._tools.values())

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
        self._categories.clear()
        logger.debug("Cleared all tools from registry")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


def create_tool(
    name: str,
    description: str,
    parameters: list[ToolParameter],
    handler: ToolHandler,
    permission_level: PermissionLevel = PermissionLevel.SAFE,
    category: str = "general",
    timeout: Optional[float] = 30.0,
) -> Tool:
    """Factory function to create a Tool with a ToolDefinition.

    Args:
        name: Tool name.
        description: Tool description.
        parameters: List of tool parameters.
        handler: Function that executes the tool.
        permission_level: Required permission level.
        category: Tool category.
        timeout: Execution timeout in seconds.

    Returns:
        A configured Tool instance.
    """
    definition = ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
    )
    return Tool(
        definition=definition,
        handler=handler,
        permission_level=permission_level,
        category=category,
        timeout=timeout,
    )
