"""Tool executor for running tools with safety guards.

The executor is responsible for validating tool arguments, checking permissions,
executing tools with timeout protection, and handling errors gracefully.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from codecrew.models.types import ToolCall, ToolResult
from codecrew.tools.permissions import (
    PermissionDeniedError,
    PermissionLevel,
    PermissionManager,
)
from codecrew.tools.registry import Tool, ToolRegistry

logger = logging.getLogger(__name__)

# Errors that are transient and worth retrying
RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
    asyncio.TimeoutError,
)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


class ToolTimeoutError(Exception):
    """Raised when tool execution times out."""

    def __init__(self, tool_name: str, timeout: float) -> None:
        self.tool_name = tool_name
        self.timeout = timeout
        super().__init__(
            f"Tool '{tool_name}' execution timed out after {timeout} seconds"
        )


class ToolValidationError(Exception):
    """Raised when tool arguments fail validation."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' validation failed: {message}")


@dataclass
class ToolExecutionResult:
    """Result of a tool execution.

    Attributes:
        tool_call_id: ID of the tool call that was executed.
        tool_name: Name of the tool that was executed.
        success: Whether execution was successful.
        result: The result value if successful.
        error: Error message if execution failed.
        execution_time: Time taken to execute in seconds.
        timestamp: When execution completed.
    """

    tool_call_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_tool_result(self) -> ToolResult:
        """Convert to a ToolResult for model consumption.

        Returns:
            ToolResult with content and error flag set appropriately.
        """
        if self.success:
            # Convert result to string for model consumption
            content = self._format_result(self.result)
        else:
            content = self._format_error()

        return ToolResult(
            tool_call_id=self.tool_call_id,
            content=content,
            is_error=not self.success,
        )

    def _format_error(self) -> str:
        """Format error with actionable guidance.

        Provides helpful suggestions based on common error patterns
        to help the model recover from failures.

        Returns:
            Formatted error string with suggestions.
        """
        error_lines = [f"Error: {self.error}", f"Tool: {self.tool_name}"]
        error_lower = (self.error or "").lower()

        # Add actionable suggestions based on error type
        if "not found" in error_lower or "no such file" in error_lower:
            error_lines.append(
                "Suggestion: Use list_directory or search_files to find the correct path."
            )
        elif "permission" in error_lower or "denied" in error_lower:
            error_lines.append(
                "Suggestion: Check if the path is within allowed directories, "
                "or if the operation requires elevated permissions."
            )
        elif "timeout" in error_lower:
            error_lines.append(
                "Suggestion: The operation took too long. Try with a smaller "
                "scope or break it into multiple smaller operations."
            )
        elif "validation" in error_lower or "invalid" in error_lower:
            error_lines.append(
                "Suggestion: Check the argument types and values. "
                "Use the correct format as specified in the tool definition."
            )
        elif "encoding" in error_lower or "decode" in error_lower:
            error_lines.append(
                "Suggestion: The file may be binary or use a non-UTF8 encoding. "
                "Try specifying the encoding or check if it's a binary file."
            )
        elif "connection" in error_lower or "network" in error_lower:
            error_lines.append(
                "Suggestion: Network connectivity issue. The operation may succeed if retried."
            )

        return "\n".join(error_lines)

    def _format_result(self, result: Any) -> str:
        """Format the result for model consumption.

        Args:
            result: The raw result value.

        Returns:
            String representation of the result.
        """
        if result is None:
            return "Success (no output)"

        if isinstance(result, str):
            return result

        if isinstance(result, (list, dict)):
            import json

            try:
                return json.dumps(result, indent=2, default=str)
            except (TypeError, ValueError):
                return str(result)

        return str(result)


@dataclass
class ToolExecutor:
    """Executes tools with safety guards and permission checks.

    The executor validates arguments, checks permissions, runs tools with
    timeout protection, and returns structured results.

    Example:
        >>> executor = ToolExecutor(registry, permissions)
        >>> result = await executor.execute(tool_call)
        >>> if result.success:
        ...     print(result.result)
        ... else:
        ...     print(f"Error: {result.error}")
    """

    registry: ToolRegistry
    permissions: PermissionManager
    default_timeout: float = 30.0
    max_output_length: int = 100000  # Max characters in result

    async def execute(
        self,
        tool_call: ToolCall,
        require_confirmation: bool = True,
    ) -> ToolExecutionResult:
        """Execute a tool call.

        Args:
            tool_call: The tool call to execute.
            require_confirmation: Whether to require user confirmation
                                 for sensitive operations.

        Returns:
            ToolExecutionResult with success/failure status and result.
        """
        start_time = asyncio.get_event_loop().time()
        tool_name = tool_call.name

        try:
            # Get the tool
            tool = self.registry.get_enabled(tool_name)
            if tool is None:
                if self.registry.has(tool_name):
                    raise ToolExecutionError(
                        tool_name, "Tool is disabled"
                    )
                raise ToolNotFoundError(tool_name)

            # Validate arguments
            self._validate_arguments(tool, tool_call.arguments)

            # Check permissions
            granted = self.permissions.check_permission(
                tool_name=tool_name,
                arguments=tool_call.arguments,
                permission_level=tool.permission_level,
                description=tool.description,
                require_confirmation=require_confirmation,
            )

            if not granted:
                raise PermissionDeniedError(
                    tool_name=tool_name,
                    reason="User denied permission",
                    required_level=tool.permission_level,
                )

            # Execute with timeout
            timeout = tool.timeout or self.default_timeout
            result = await self._execute_with_timeout(
                tool, tool_call.arguments, timeout
            )

            # Truncate overly long results
            if isinstance(result, str) and len(result) > self.max_output_length:
                result = (
                    result[: self.max_output_length]
                    + f"\n... (truncated, {len(result)} total characters)"
                )

            execution_time = asyncio.get_event_loop().time() - start_time

            logger.info(
                f"Tool executed successfully: {tool_name} "
                f"(took {execution_time:.2f}s)"
            )

            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time=execution_time,
            )

        except RETRYABLE_ERRORS as e:
            # Mark retryable errors distinctly
            logger.warning(f"Retryable error for tool {tool_name}: {e}")
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=f"Transient error (retryable): {type(e).__name__}: {e}",
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

        except ToolNotFoundError as e:
            logger.warning(f"Tool not found: {tool_name}")
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

        except PermissionDeniedError as e:
            logger.warning(f"Permission denied: {tool_name} - {e.reason}")
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

        except ToolTimeoutError as e:
            logger.error(f"Tool timeout: {tool_name}")
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

        except ToolValidationError as e:
            logger.warning(f"Validation failed: {tool_name}")
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

        except Exception as e:
            logger.error(
                f"Tool execution error: {tool_name} - {e}\n"
                f"{traceback.format_exc()}"
            )
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                success=False,
                error=f"Execution error: {type(e).__name__}: {e}",
                execution_time=asyncio.get_event_loop().time() - start_time,
            )

    async def execute_with_retry(
        self,
        tool_call: ToolCall,
        require_confirmation: bool = True,
        max_retries: int = 2,
        base_delay: float = 0.5,
    ) -> ToolExecutionResult:
        """Execute a tool call with automatic retry for transient failures.

        Implements exponential backoff for retryable errors like timeouts,
        connection errors, and OS errors.

        Args:
            tool_call: The tool call to execute.
            require_confirmation: Whether to require user confirmation
                                 for sensitive operations.
            max_retries: Maximum number of retry attempts (default: 2).
            base_delay: Base delay in seconds between retries (default: 0.5).
                       Actual delay is base_delay * (attempt + 1) for backoff.

        Returns:
            ToolExecutionResult with success/failure status and result.
        """
        last_result: Optional[ToolExecutionResult] = None

        for attempt in range(max_retries + 1):
            result = await self.execute(tool_call, require_confirmation)

            # Success - return immediately
            if result.success:
                if attempt > 0:
                    logger.info(
                        f"Tool {tool_call.name} succeeded after {attempt} retries"
                    )
                return result

            last_result = result

            # Check if error is retryable
            is_retryable = (
                result.error is not None
                and "transient error" in result.error.lower()
            )

            # If not retryable or out of retries, return the result
            if not is_retryable or attempt == max_retries:
                if attempt > 0:
                    logger.warning(
                        f"Tool {tool_call.name} failed after {attempt + 1} attempts"
                    )
                return result

            # Calculate delay with exponential backoff
            delay = base_delay * (attempt + 1)
            logger.info(
                f"Retrying tool {tool_call.name} in {delay}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(delay)

        # Should not reach here, but return last result just in case
        return last_result or ToolExecutionResult(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            success=False,
            error="Unexpected retry loop exit",
        )

    async def execute_batch(
        self,
        tool_calls: list[ToolCall],
        require_confirmation: bool = True,
        parallel: bool = False,
    ) -> list[ToolExecutionResult]:
        """Execute multiple tool calls.

        Args:
            tool_calls: List of tool calls to execute.
            require_confirmation: Whether to require user confirmation.
            parallel: If True, execute tools concurrently.

        Returns:
            List of execution results in the same order as inputs.
        """
        if parallel:
            tasks = [
                self.execute(tc, require_confirmation) for tc in tool_calls
            ]
            return await asyncio.gather(*tasks)

        # Sequential execution
        results = []
        for tool_call in tool_calls:
            result = await self.execute(tool_call, require_confirmation)
            results.append(result)
        return results

    def _validate_arguments(
        self, tool: Tool, arguments: dict[str, Any]
    ) -> None:
        """Validate tool arguments against the tool definition.

        Args:
            tool: The tool being called.
            arguments: The arguments provided.

        Raises:
            ToolValidationError: If validation fails.
        """
        definition = tool.definition

        # Check required parameters
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                raise ToolValidationError(
                    tool.name,
                    f"Missing required parameter: {param.name}",
                )

        # Check for unknown parameters
        known_params = {p.name for p in definition.parameters}
        for arg_name in arguments:
            if arg_name not in known_params:
                raise ToolValidationError(
                    tool.name,
                    f"Unknown parameter: {arg_name}",
                )

        # Validate parameter types and enums
        for param in definition.parameters:
            if param.name not in arguments:
                continue

            value = arguments[param.name]

            # Check enum constraints
            if param.enum and value not in param.enum:
                raise ToolValidationError(
                    tool.name,
                    f"Parameter '{param.name}' must be one of: {param.enum}",
                )

            # Basic type validation
            if not self._validate_type(value, param.type):
                raise ToolValidationError(
                    tool.name,
                    f"Parameter '{param.name}' has invalid type. "
                    f"Expected {param.type}, got {type(value).__name__}",
                )

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate a value against an expected JSON Schema type.

        Args:
            value: The value to validate.
            expected_type: The expected JSON Schema type.

        Returns:
            True if the value matches the expected type.
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type)
        if expected is None:
            # Unknown type, allow anything
            return True

        return isinstance(value, expected)

    async def _execute_with_timeout(
        self,
        tool: Tool,
        arguments: dict[str, Any],
        timeout: float,
    ) -> Any:
        """Execute a tool handler with timeout protection.

        Args:
            tool: The tool to execute.
            arguments: Arguments for the tool.
            timeout: Maximum execution time in seconds.

        Returns:
            The tool's return value.

        Raises:
            ToolTimeoutError: If execution times out.
            Exception: Any exception raised by the handler.
        """
        handler = tool.handler

        # Check if handler is async
        if inspect.iscoroutinefunction(handler):
            coro = handler(arguments)
        else:
            # Run sync handler in thread pool
            loop = asyncio.get_event_loop()
            coro = loop.run_in_executor(None, handler, arguments)

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise ToolTimeoutError(tool.name, timeout)

    def get_tool_results(
        self, results: list[ToolExecutionResult]
    ) -> list[ToolResult]:
        """Convert execution results to ToolResults for model consumption.

        Args:
            results: List of execution results.

        Returns:
            List of ToolResults.
        """
        return [r.to_tool_result() for r in results]
