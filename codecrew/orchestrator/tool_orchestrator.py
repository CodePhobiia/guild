"""Tool-enabled orchestrator for CodeCrew.

This module provides a ToolEnabledOrchestrator that wraps the base Orchestrator
and adds automatic tool execution capabilities, including:
- Tool execution loop (model -> tool -> model feedback)
- Permission handling via events
- Tool result injection into conversation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional

from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    ToolCall,
    ToolResult,
    Usage,
)
from codecrew.tools.context import ToolContext

from .engine import Orchestrator
from .events import EventType, OrchestratorEvent

if TYPE_CHECKING:
    from codecrew.config import Settings
    from codecrew.models.base import ModelClient
    from codecrew.tools import ToolExecutor, ToolRegistry


logger = logging.getLogger(__name__)

# Tools that are known to be safe for parallel execution (read-only)
PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "list_directory",
    "search_files",
})


class ToolEnabledOrchestrator(Orchestrator):
    """Orchestrator with integrated tool execution capabilities.

    This extends the base Orchestrator to:
    1. Execute tools when models request them
    2. Feed tool results back to models for continued generation
    3. Handle permission requests via events
    4. Support multi-turn tool use conversations

    Example:
        >>> orchestrator = ToolEnabledOrchestrator(
        ...     clients=clients,
        ...     settings=settings,
        ...     tool_executor=executor,
        ...     tool_registry=registry,
        ... )
        >>> async for event in orchestrator.process_message("Read file.txt"):
        ...     if event.type == EventType.TOOL_RESULT:
        ...         print(f"Tool result: {event.tool_result.content}")
    """

    def __init__(
        self,
        clients: dict[str, "ModelClient"],
        settings: "Settings",
        tool_executor: "ToolExecutor",
        tool_registry: "ToolRegistry",
        max_tool_iterations: int = 10,
        enable_parallel_tools: bool = True,
        **kwargs,
    ):
        """Initialize the tool-enabled orchestrator.

        Args:
            clients: Model clients.
            settings: Application settings.
            tool_executor: Executor for running tools.
            tool_registry: Registry of available tools.
            max_tool_iterations: Max tool execution loops per turn.
            enable_parallel_tools: If True, execute parallel-safe tools concurrently.
            **kwargs: Additional args passed to base Orchestrator.
        """
        super().__init__(clients=clients, settings=settings, **kwargs)
        self.tool_executor = tool_executor
        self.tool_registry = tool_registry
        self.max_tool_iterations = max_tool_iterations
        self.enable_parallel_tools = enable_parallel_tools
        self.tool_context = ToolContext()

    def get_tool_definitions(self):
        """Get tool definitions for passing to model clients.

        Returns:
            List of ToolDefinition objects.
        """
        return self.tool_registry.get_definitions()

    async def _stream_response(
        self,
        client: "ModelClient",
        model_name: str,
        messages: list[Message],
        system: Optional[str],
    ) -> AsyncIterator[OrchestratorEvent]:
        """Stream a response from a model with tool execution support.

        Overrides the base method to:
        1. Pass tool definitions to the model
        2. Execute tools when requested
        3. Loop back with tool results
        """
        tools = self.get_tool_definitions()
        iteration = 0

        while iteration < self.max_tool_iterations:
            iteration += 1

            content_buffer = ""
            tool_calls: list[ToolCall] = []
            finish_reason = FinishReason.STOP
            usage: Optional[Usage] = None

            async for chunk in client.generate_stream(
                messages=messages,
                system=system,
                tools=tools if tools else None,
            ):
                if chunk.content:
                    content_buffer += chunk.content
                    yield OrchestratorEvent.response_chunk(model_name, chunk.content)

                if chunk.tool_call:
                    tool_calls.append(chunk.tool_call)
                    yield OrchestratorEvent.tool_call_event(model_name, chunk.tool_call)

                if chunk.is_complete:
                    finish_reason = chunk.finish_reason or FinishReason.STOP
                    usage = chunk.usage

            # Build response
            response = ModelResponse(
                content=content_buffer,
                model=model_name,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
                usage=usage,
            )

            # Add assistant message to conversation
            assistant_msg = Message.assistant(content_buffer, model=model_name)
            assistant_msg.tool_calls = tool_calls
            self.add_message(assistant_msg)

            # Check if we need to execute tools
            if finish_reason == FinishReason.TOOL_USE and tool_calls:
                # Execute tools and get results
                tool_results = await self._execute_tools(model_name, tool_calls)

                # Yield tool result events
                for result in tool_results:
                    yield OrchestratorEvent.tool_result_event(model_name, result)

                # Add tool results to conversation
                tool_msg = Message.tool_results(tool_results)
                self.add_message(tool_msg)

                # Update messages for next iteration (including new messages)
                messages = self._conversation.copy()

                # Continue the loop to get model's response to tool results
                continue

            # No tool calls or done with tools - complete the response
            yield OrchestratorEvent.response_complete(model_name, response)
            return

        # Max iterations reached
        logger.warning(
            f"Max tool iterations ({self.max_tool_iterations}) reached for {model_name}"
        )
        yield OrchestratorEvent.error_event(
            f"Maximum tool iterations ({self.max_tool_iterations}) reached",
            model=model_name,
        )

    async def _generate_response(
        self,
        client: "ModelClient",
        model_name: str,
        messages: list[Message],
        system: Optional[str],
    ) -> AsyncIterator[OrchestratorEvent]:
        """Generate a non-streaming response with tool execution support.

        Overrides the base method to handle tool execution.
        """
        tools = self.get_tool_definitions()
        iteration = 0

        while iteration < self.max_tool_iterations:
            iteration += 1

            response = await client.generate(
                messages=messages,
                system=system,
                tools=tools if tools else None,
            )

            # Add assistant message to conversation
            assistant_msg = Message.assistant(response.content, model=model_name)
            assistant_msg.tool_calls = response.tool_calls
            self.add_message(assistant_msg)

            # Emit content as single chunk
            if response.content:
                yield OrchestratorEvent.response_chunk(model_name, response.content)

            # Emit tool call events
            for tc in response.tool_calls:
                yield OrchestratorEvent.tool_call_event(model_name, tc)

            # Check if we need to execute tools
            if response.finish_reason == FinishReason.TOOL_USE and response.tool_calls:
                # Execute tools
                tool_results = await self._execute_tools(model_name, response.tool_calls)

                # Yield tool result events
                for result in tool_results:
                    yield OrchestratorEvent.tool_result_event(model_name, result)

                # Add tool results to conversation
                tool_msg = Message.tool_results(tool_results)
                self.add_message(tool_msg)

                # Update messages for next iteration
                messages = self._conversation.copy()
                continue

            # Done with tool execution
            yield OrchestratorEvent.response_complete(model_name, response)
            return

        # Max iterations reached
        logger.warning(
            f"Max tool iterations ({self.max_tool_iterations}) reached for {model_name}"
        )
        yield OrchestratorEvent.error_event(
            f"Maximum tool iterations ({self.max_tool_iterations}) reached",
            model=model_name,
        )

    def _classify_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> tuple[list[ToolCall], list[ToolCall]]:
        """Classify tool calls into parallel-safe and sequential groups.

        Args:
            tool_calls: List of tool calls to classify.

        Returns:
            Tuple of (parallel_safe_calls, sequential_calls).
        """
        parallel_calls: list[ToolCall] = []
        sequential_calls: list[ToolCall] = []

        for call in tool_calls:
            tool = self.tool_registry.get(call.name)

            # Check if tool is parallel-safe (either by name or by flag)
            is_parallel_safe = (
                call.name in PARALLEL_SAFE_TOOLS
                or (tool is not None and tool.parallel_safe)
            )

            if is_parallel_safe:
                parallel_calls.append(call)
            else:
                sequential_calls.append(call)

        return parallel_calls, sequential_calls

    def _reorder_results(
        self,
        original_calls: list[ToolCall],
        results: list[ToolResult],
    ) -> list[ToolResult]:
        """Reorder results to match the original call order.

        Args:
            original_calls: Original tool calls in order.
            results: Results that may be in different order.

        Returns:
            Results in same order as original calls.
        """
        # Create mapping from tool_call_id to result
        result_map = {r.tool_call_id: r for r in results}

        # Return results in original order
        return [result_map[call.id] for call in original_calls if call.id in result_map]

    async def _execute_tools(
        self,
        model_name: str,
        tool_calls: list[ToolCall],
    ) -> list[ToolResult]:
        """Execute a list of tool calls with parallel optimization.

        Parallel-safe tools (read-only operations) are executed concurrently,
        while sequential tools (writes, edits) are executed in order.

        Args:
            model_name: Model that requested the tools.
            tool_calls: Tool calls to execute.

        Returns:
            List of tool results in the same order as input calls.
        """
        if not tool_calls:
            return []

        results: list[ToolResult] = []

        if self.enable_parallel_tools:
            # Classify tools into parallel-safe and sequential
            parallel_calls, sequential_calls = self._classify_tool_calls(tool_calls)

            # Execute parallel-safe tools concurrently
            if parallel_calls:
                logger.info(
                    f"Executing {len(parallel_calls)} parallel-safe tools for {model_name}"
                )
                parallel_results = await self.tool_executor.execute_batch(
                    tool_calls=parallel_calls,
                    parallel=True,
                    require_confirmation=True,
                )
                for exec_result in parallel_results:
                    results.append(exec_result.to_tool_result())
                    self._log_tool_result(exec_result)

            # Execute sequential tools in order
            for tool_call in sequential_calls:
                logger.info(f"Executing tool: {tool_call.name} for {model_name}")
                exec_result = await self.tool_executor.execute(
                    tool_call=tool_call,
                    require_confirmation=True,
                )
                results.append(exec_result.to_tool_result())
                self._log_tool_result(exec_result)

                # Track modifications in context
                if exec_result.success and tool_call.name in ("write_file", "edit_file"):
                    path = tool_call.arguments.get("path", "unknown")
                    operation = "write" if tool_call.name == "write_file" else "edit"
                    self.tool_context.record_modification(path, operation)

            # Reorder results to match original call order
            results = self._reorder_results(tool_calls, results)

        else:
            # Sequential execution for all tools (original behavior)
            for tool_call in tool_calls:
                logger.info(f"Executing tool: {tool_call.name} for {model_name}")
                exec_result = await self.tool_executor.execute(
                    tool_call=tool_call,
                    require_confirmation=True,
                )
                results.append(exec_result.to_tool_result())
                self._log_tool_result(exec_result)

                # Track modifications in context
                if exec_result.success and tool_call.name in ("write_file", "edit_file"):
                    path = tool_call.arguments.get("path", "unknown")
                    operation = "write" if tool_call.name == "write_file" else "edit"
                    self.tool_context.record_modification(path, operation)

        return results

    def _log_tool_result(self, exec_result) -> None:
        """Log the result of a tool execution.

        Args:
            exec_result: The ToolExecutionResult from execution.
        """
        if exec_result.success:
            logger.debug(
                f"Tool {exec_result.tool_name} completed successfully "
                f"({exec_result.execution_time:.2f}s)"
            )
        else:
            logger.warning(
                f"Tool {exec_result.tool_name} failed: {exec_result.error}"
            )

    def get_tool_context_summary(self) -> str:
        """Get a summary of tool activity in this session.

        Returns:
            Human-readable summary of file modifications.
        """
        return self.tool_context.get_modification_summary()

    def clear_tool_context(self) -> None:
        """Clear the tool context tracking data."""
        self.tool_context.clear()


def create_tool_enabled_orchestrator(
    clients: dict[str, "ModelClient"],
    settings: "Settings",
    tool_executor: "ToolExecutor",
    tool_registry: "ToolRegistry",
    max_tool_iterations: int = 10,
    enable_parallel_tools: bool = True,
) -> ToolEnabledOrchestrator:
    """Factory function to create a tool-enabled orchestrator.

    Args:
        clients: Model clients.
        settings: Application settings.
        tool_executor: Tool executor instance.
        tool_registry: Tool registry instance.
        max_tool_iterations: Maximum tool execution loops.
        enable_parallel_tools: If True, execute parallel-safe tools concurrently.

    Returns:
        Configured ToolEnabledOrchestrator.
    """
    # Determine turn strategy from settings
    strategy = settings.conversation.first_responder
    if strategy not in ("rotate", "confidence", "fixed"):
        strategy = "rotate"

    return ToolEnabledOrchestrator(
        clients=clients,
        settings=settings,
        tool_executor=tool_executor,
        tool_registry=tool_registry,
        max_tool_iterations=max_tool_iterations,
        enable_parallel_tools=enable_parallel_tools,
        turn_strategy=strategy,  # type: ignore
    )
