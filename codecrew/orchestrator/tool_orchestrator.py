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

from .engine import Orchestrator
from .events import EventType, OrchestratorEvent

if TYPE_CHECKING:
    from codecrew.config import Settings
    from codecrew.models.base import ModelClient
    from codecrew.tools import ToolExecutor, ToolRegistry


logger = logging.getLogger(__name__)


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
        **kwargs,
    ):
        """Initialize the tool-enabled orchestrator.

        Args:
            clients: Model clients.
            settings: Application settings.
            tool_executor: Executor for running tools.
            tool_registry: Registry of available tools.
            max_tool_iterations: Max tool execution loops per turn.
            **kwargs: Additional args passed to base Orchestrator.
        """
        super().__init__(clients=clients, settings=settings, **kwargs)
        self.tool_executor = tool_executor
        self.tool_registry = tool_registry
        self.max_tool_iterations = max_tool_iterations

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

    async def _execute_tools(
        self,
        model_name: str,
        tool_calls: list[ToolCall],
    ) -> list[ToolResult]:
        """Execute a list of tool calls.

        Args:
            model_name: Model that requested the tools.
            tool_calls: Tool calls to execute.

        Returns:
            List of tool results.
        """
        results = []

        for tool_call in tool_calls:
            logger.info(f"Executing tool: {tool_call.name} for {model_name}")

            # Execute the tool
            execution_result = await self.tool_executor.execute(
                tool_call=tool_call,
                require_confirmation=True,
            )

            # Convert to ToolResult
            tool_result = execution_result.to_tool_result()
            results.append(tool_result)

            if execution_result.success:
                logger.debug(
                    f"Tool {tool_call.name} completed successfully "
                    f"({execution_result.execution_time:.2f}s)"
                )
            else:
                logger.warning(
                    f"Tool {tool_call.name} failed: {execution_result.error}"
                )

        return results


def create_tool_enabled_orchestrator(
    clients: dict[str, "ModelClient"],
    settings: "Settings",
    tool_executor: "ToolExecutor",
    tool_registry: "ToolRegistry",
    max_tool_iterations: int = 10,
) -> ToolEnabledOrchestrator:
    """Factory function to create a tool-enabled orchestrator.

    Args:
        clients: Model clients.
        settings: Application settings.
        tool_executor: Tool executor instance.
        tool_registry: Tool registry instance.
        max_tool_iterations: Maximum tool execution loops.

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
        turn_strategy=strategy,  # type: ignore
    )
