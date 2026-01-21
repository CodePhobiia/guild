"""Permission system for tool execution.

This module provides a permission management system that controls which tools
can be executed and under what conditions. It supports different permission
levels and can request user confirmation for sensitive operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for tool execution.

    Levels are ordered from least to most restrictive:
    - SAFE: No confirmation needed, safe read-only operations
    - CAUTIOUS: Confirmation recommended, may modify state
    - DANGEROUS: Always requires confirmation, potentially destructive
    - BLOCKED: Never allowed, must be explicitly unblocked
    """

    SAFE = "safe"
    CAUTIOUS = "cautious"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"

    def requires_confirmation(self) -> bool:
        """Check if this level typically requires user confirmation."""
        return self in (PermissionLevel.CAUTIOUS, PermissionLevel.DANGEROUS)

    def __lt__(self, other: "PermissionLevel") -> bool:
        """Compare permission levels (SAFE < CAUTIOUS < DANGEROUS < BLOCKED)."""
        order = [
            PermissionLevel.SAFE,
            PermissionLevel.CAUTIOUS,
            PermissionLevel.DANGEROUS,
            PermissionLevel.BLOCKED,
        ]
        return order.index(self) < order.index(other)

    def __le__(self, other: "PermissionLevel") -> bool:
        return self == other or self < other


class PermissionDeniedError(Exception):
    """Raised when a tool execution is denied due to permissions."""

    def __init__(
        self,
        tool_name: str,
        reason: str,
        required_level: Optional[PermissionLevel] = None,
    ) -> None:
        self.tool_name = tool_name
        self.reason = reason
        self.required_level = required_level
        super().__init__(f"Permission denied for tool '{tool_name}': {reason}")


@dataclass
class PermissionRequest:
    """A request for permission to execute a tool.

    This is passed to the confirmation callback when user input is needed.

    Attributes:
        tool_name: Name of the tool requesting permission.
        arguments: Arguments that will be passed to the tool.
        permission_level: The tool's permission level.
        description: Human-readable description of what the tool will do.
        timestamp: When the request was created.
    """

    tool_name: str
    arguments: dict[str, Any]
    permission_level: PermissionLevel
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format_for_display(self) -> str:
        """Format the request for user display.

        Returns:
            A human-readable string describing the permission request.
        """
        lines = [
            f"Tool: {self.tool_name}",
            f"Level: {self.permission_level.value}",
            f"Description: {self.description}",
            "Arguments:",
        ]
        for key, value in self.arguments.items():
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:97] + "..."
            lines.append(f"  {key}: {str_value}")
        return "\n".join(lines)


# Type alias for confirmation callback
# Returns True if permission is granted, False otherwise
ConfirmationCallback = Callable[[PermissionRequest], bool]


@dataclass
class PermissionManager:
    """Manages permissions for tool execution.

    The permission manager controls which tools can be executed and handles
    user confirmation for sensitive operations. It supports:
    - Auto-approve mode for automated/trusted scenarios
    - Per-tool permission overrides
    - Session-based grants (remembered until cleared)
    - Blocked tool list

    Example:
        >>> manager = PermissionManager()
        >>> manager.set_confirmation_callback(my_confirm_func)
        >>>
        >>> # Check if tool can be executed
        >>> if manager.check_permission("read_file", args, PermissionLevel.SAFE):
        ...     result = await executor.execute(...)
    """

    # Auto-approve all operations (for testing or trusted scenarios)
    auto_approve: bool = False

    # Maximum permission level that's auto-approved without confirmation
    auto_approve_level: PermissionLevel = PermissionLevel.SAFE

    # Per-tool permission overrides (tool_name -> level)
    _tool_overrides: dict[str, PermissionLevel] = field(default_factory=dict)

    # Tools that have been granted permission this session
    _session_grants: set[str] = field(default_factory=set)

    # Blocked tools (never allowed)
    _blocked_tools: set[str] = field(default_factory=set)

    # Callback for requesting user confirmation
    _confirmation_callback: Optional[ConfirmationCallback] = None

    def set_confirmation_callback(self, callback: ConfirmationCallback) -> None:
        """Set the callback function for user confirmation.

        Args:
            callback: Function that takes a PermissionRequest and returns
                     True if permission is granted.
        """
        self._confirmation_callback = callback

    def block_tool(self, tool_name: str) -> None:
        """Block a tool from being executed.

        Args:
            tool_name: Name of the tool to block.
        """
        self._blocked_tools.add(tool_name)
        # Remove from session grants if present
        self._session_grants.discard(tool_name)
        logger.info(f"Blocked tool: {tool_name}")

    def unblock_tool(self, tool_name: str) -> None:
        """Unblock a previously blocked tool.

        Args:
            tool_name: Name of the tool to unblock.
        """
        self._blocked_tools.discard(tool_name)
        logger.info(f"Unblocked tool: {tool_name}")

    def is_blocked(self, tool_name: str) -> bool:
        """Check if a tool is blocked.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if the tool is blocked.
        """
        return tool_name in self._blocked_tools

    def set_tool_permission(
        self, tool_name: str, level: PermissionLevel
    ) -> None:
        """Override the permission level for a specific tool.

        Args:
            tool_name: Name of the tool.
            level: New permission level to apply.
        """
        self._tool_overrides[tool_name] = level
        logger.debug(f"Set permission override for {tool_name}: {level.value}")

    def clear_tool_permission(self, tool_name: str) -> None:
        """Remove a permission override for a tool.

        Args:
            tool_name: Name of the tool.
        """
        self._tool_overrides.pop(tool_name, None)

    def get_effective_level(
        self, tool_name: str, default_level: PermissionLevel
    ) -> PermissionLevel:
        """Get the effective permission level for a tool.

        Args:
            tool_name: Name of the tool.
            default_level: The tool's default permission level.

        Returns:
            The effective permission level (override if set, else default).
        """
        return self._tool_overrides.get(tool_name, default_level)

    def grant_session_permission(self, tool_name: str) -> None:
        """Grant permission for a tool for the current session.

        This remembers that the user approved this tool, so subsequent
        executions won't require confirmation.

        Args:
            tool_name: Name of the tool.
        """
        self._session_grants.add(tool_name)
        logger.debug(f"Granted session permission for: {tool_name}")

    def has_session_permission(self, tool_name: str) -> bool:
        """Check if a tool has been granted session permission.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if the tool was previously approved this session.
        """
        return tool_name in self._session_grants

    def revoke_session_permission(self, tool_name: str) -> None:
        """Revoke session permission for a tool.

        Args:
            tool_name: Name of the tool.
        """
        self._session_grants.discard(tool_name)

    def clear_session_grants(self) -> None:
        """Clear all session permission grants."""
        self._session_grants.clear()
        logger.debug("Cleared all session permission grants")

    def check_permission(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        permission_level: PermissionLevel,
        description: str = "",
        require_confirmation: bool = True,
    ) -> bool:
        """Check if a tool execution is permitted.

        This method checks various permission rules and may request user
        confirmation if needed.

        Args:
            tool_name: Name of the tool.
            arguments: Arguments for the tool.
            permission_level: The tool's permission level.
            description: Human-readable description of the operation.
            require_confirmation: If False, skip user confirmation.

        Returns:
            True if execution is permitted.

        Raises:
            PermissionDeniedError: If the tool is blocked.
        """
        # Check if tool is blocked
        if self.is_blocked(tool_name):
            raise PermissionDeniedError(
                tool_name=tool_name,
                reason="Tool is blocked",
                required_level=PermissionLevel.BLOCKED,
            )

        # Get effective permission level
        effective_level = self.get_effective_level(tool_name, permission_level)

        # Auto-approve mode
        if self.auto_approve:
            logger.debug(f"Auto-approved: {tool_name}")
            return True

        # Check if level is within auto-approve threshold
        if effective_level <= self.auto_approve_level:
            logger.debug(f"Auto-approved (level {effective_level.value}): {tool_name}")
            return True

        # Check session grants
        if self.has_session_permission(tool_name):
            logger.debug(f"Session permission exists: {tool_name}")
            return True

        # If confirmation not required, approve
        if not require_confirmation:
            return True

        # Request user confirmation
        if self._confirmation_callback is None:
            # No callback set, deny by default for safety
            logger.warning(
                f"No confirmation callback set, denying: {tool_name}"
            )
            return False

        request = PermissionRequest(
            tool_name=tool_name,
            arguments=arguments,
            permission_level=effective_level,
            description=description or f"Execute tool: {tool_name}",
        )

        granted = self._confirmation_callback(request)

        if granted:
            # Remember the grant for this session
            self.grant_session_permission(tool_name)
            logger.info(f"Permission granted by user: {tool_name}")
        else:
            logger.info(f"Permission denied by user: {tool_name}")

        return granted

    def list_blocked_tools(self) -> list[str]:
        """List all blocked tools.

        Returns:
            List of blocked tool names.
        """
        return list(self._blocked_tools)

    def list_session_grants(self) -> list[str]:
        """List all tools with session permission grants.

        Returns:
            List of granted tool names.
        """
        return list(self._session_grants)

    def list_overrides(self) -> dict[str, PermissionLevel]:
        """List all permission overrides.

        Returns:
            Dict mapping tool names to their override levels.
        """
        return dict(self._tool_overrides)
