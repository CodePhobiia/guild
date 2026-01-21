"""Centralized exception hierarchy for CodeCrew.

This module defines all custom exceptions used throughout the CodeCrew
application, organized in a hierarchy for easy handling and specificity.
"""

from __future__ import annotations

from typing import Any, Optional


class CodeCrewError(Exception):
    """Base exception for all CodeCrew errors.

    Attributes:
        message: Human-readable error message.
        code: Optional error code for programmatic handling.
        details: Optional dictionary with additional error context.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationError(CodeCrewError):
    """Raised when there's a configuration problem."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Raised when a required API key is not configured."""

    def __init__(self, provider: str):
        super().__init__(
            message=f"API key for {provider} is not configured",
            code="MISSING_API_KEY",
            details={"provider": provider},
        )


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            message=f"Invalid configuration for '{field}': {reason}",
            code="INVALID_CONFIG",
            details={"field": field, "value": str(value)[:100], "reason": reason},
        )


# =============================================================================
# Model Errors
# =============================================================================

class ModelError(CodeCrewError):
    """Base exception for AI model-related errors."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if model:
            details["model"] = model
        super().__init__(message, code, details)


class APIError(ModelError):
    """Raised when an API call fails."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        details = {}
        if status_code:
            details["status_code"] = status_code
        if response_body:
            # Truncate response body to avoid logging sensitive data
            details["response_body"] = response_body[:500]
        super().__init__(message, model, "API_ERROR", details)


class RateLimitError(ModelError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        model: str,
        retry_after: Optional[float] = None,
    ):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            message=f"Rate limit exceeded for {model}",
            model=model,
            code="RATE_LIMIT",
            details=details,
        )


class AuthenticationError(ModelError):
    """Raised when API authentication fails."""

    def __init__(self, model: str, reason: Optional[str] = None):
        message = f"Authentication failed for {model}"
        if reason:
            message += f": {reason}"
        super().__init__(message, model, "AUTH_ERROR")


class ModelUnavailableError(ModelError):
    """Raised when a model is not available."""

    def __init__(self, model: str, reason: Optional[str] = None):
        message = f"Model {model} is not available"
        if reason:
            message += f": {reason}"
        super().__init__(message, model, "MODEL_UNAVAILABLE")


class GenerationError(ModelError):
    """Raised when response generation fails."""

    def __init__(self, model: str, reason: str):
        super().__init__(
            message=f"Generation failed for {model}: {reason}",
            model=model,
            code="GENERATION_ERROR",
        )


# =============================================================================
# Tool Errors
# =============================================================================

class ToolError(CodeCrewError):
    """Base exception for tool-related errors."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, code, details)


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found."""

    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Tool '{tool_name}' not found",
            tool_name=tool_name,
            code="TOOL_NOT_FOUND",
        )


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""

    def __init__(
        self,
        tool_name: str,
        reason: str,
        original_error: Optional[Exception] = None,
    ):
        details = {"reason": reason}
        if original_error:
            details["original_error"] = str(original_error)
            details["original_type"] = type(original_error).__name__
        super().__init__(
            message=f"Tool '{tool_name}' failed: {reason}",
            tool_name=tool_name,
            code="TOOL_EXECUTION_ERROR",
            details=details,
        )


class ToolValidationError(ToolError):
    """Raised when tool arguments fail validation."""

    def __init__(
        self,
        tool_name: str,
        parameter: str,
        reason: str,
    ):
        super().__init__(
            message=f"Invalid argument '{parameter}' for tool '{tool_name}': {reason}",
            tool_name=tool_name,
            code="TOOL_VALIDATION_ERROR",
            details={"parameter": parameter, "reason": reason},
        )


class ToolTimeoutError(ToolError):
    """Raised when tool execution times out."""

    def __init__(self, tool_name: str, timeout: float):
        super().__init__(
            message=f"Tool '{tool_name}' timed out after {timeout}s",
            tool_name=tool_name,
            code="TOOL_TIMEOUT",
            details={"timeout_seconds": timeout},
        )


class PermissionDeniedError(ToolError):
    """Raised when tool execution is denied due to permissions."""

    def __init__(
        self,
        tool_name: str,
        required_level: str,
        reason: Optional[str] = None,
    ):
        message = f"Permission denied for tool '{tool_name}' (requires {required_level})"
        if reason:
            message += f": {reason}"
        super().__init__(
            message=message,
            tool_name=tool_name,
            code="PERMISSION_DENIED",
            details={"required_level": required_level},
        )


# =============================================================================
# Security Errors
# =============================================================================

class SecurityError(CodeCrewError):
    """Base exception for security-related errors."""
    pass


class PathAccessError(SecurityError):
    """Raised when a path access is denied for security reasons."""

    def __init__(self, path: str, reason: str):
        super().__init__(
            message=f"Access denied to path '{path}': {reason}",
            code="PATH_ACCESS_DENIED",
            details={"path": path, "reason": reason},
        )


class CommandBlockedError(SecurityError):
    """Raised when a shell command is blocked for security reasons."""

    def __init__(self, command: str, reason: str):
        # Don't include full command in message for security
        truncated_cmd = command[:50] + "..." if len(command) > 50 else command
        super().__init__(
            message=f"Command blocked: {reason}",
            code="COMMAND_BLOCKED",
            details={"command_preview": truncated_cmd, "reason": reason},
        )


class InputValidationError(SecurityError):
    """Raised when input validation fails."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Invalid input for '{field}': {reason}",
            code="INPUT_VALIDATION_ERROR",
            details={"field": field, "reason": reason},
        )


# =============================================================================
# Conversation Errors
# =============================================================================

class ConversationError(CodeCrewError):
    """Base exception for conversation-related errors."""
    pass


class SessionNotFoundError(ConversationError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session '{session_id}' not found",
            code="SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )


class SessionError(ConversationError):
    """Raised when there's a session-related error."""

    def __init__(self, message: str, session_id: Optional[str] = None):
        details = {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(message, "SESSION_ERROR", details)


class PersistenceError(ConversationError):
    """Raised when database operations fail."""

    def __init__(
        self,
        operation: str,
        reason: str,
        original_error: Optional[Exception] = None,
    ):
        details = {"operation": operation, "reason": reason}
        if original_error:
            details["original_error"] = str(original_error)
        super().__init__(
            message=f"Database {operation} failed: {reason}",
            code="PERSISTENCE_ERROR",
            details=details,
        )


class MessageNotFoundError(ConversationError):
    """Raised when a message is not found."""

    def __init__(self, message_id: str):
        super().__init__(
            message=f"Message '{message_id}' not found",
            code="MESSAGE_NOT_FOUND",
            details={"message_id": message_id},
        )


# =============================================================================
# Git Errors
# =============================================================================

class GitError(CodeCrewError):
    """Raised when a git operation fails."""

    def __init__(
        self,
        message: str,
        returncode: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        details = {}
        if returncode is not None:
            details["returncode"] = returncode
        if stderr:
            details["stderr"] = stderr[:500]  # Truncate for safety
        super().__init__(message, "GIT_ERROR", details)
        self.returncode = returncode
        self.stderr = stderr


class NotARepositoryError(GitError):
    """Raised when path is not a git repository."""

    def __init__(self, path: str):
        super().__init__(
            message=f"Not a git repository: {path}",
        )
        self.details["path"] = path
        self.code = "NOT_A_REPOSITORY"


# =============================================================================
# UI Errors
# =============================================================================

class UIError(CodeCrewError):
    """Base exception for UI-related errors."""
    pass


class CommandError(UIError):
    """Raised when a slash command fails."""

    def __init__(self, command: str, reason: str):
        super().__init__(
            message=f"Command '{command}' failed: {reason}",
            code="COMMAND_ERROR",
            details={"command": command, "reason": reason},
        )


class RenderError(UIError):
    """Raised when UI rendering fails."""

    def __init__(self, component: str, reason: str):
        super().__init__(
            message=f"Failed to render '{component}': {reason}",
            code="RENDER_ERROR",
            details={"component": component, "reason": reason},
        )


# =============================================================================
# Orchestration Errors
# =============================================================================

class OrchestrationError(CodeCrewError):
    """Base exception for orchestration-related errors."""
    pass


class NoModelsAvailableError(OrchestrationError):
    """Raised when no models are available for conversation."""

    def __init__(self):
        super().__init__(
            message="No AI models are available. Please configure at least one API key.",
            code="NO_MODELS_AVAILABLE",
        )


class ContextError(OrchestrationError):
    """Raised when context assembly fails."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Context assembly failed: {reason}",
            code="CONTEXT_ERROR",
        )
