"""Event handler for orchestrator events."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from codecrew.orchestrator.events import EventType, OrchestratorEvent
from codecrew.ui.components.message_list import MessageList
from codecrew.ui.components.status_bar import StatusBar
from codecrew.ui.components.tool_panel import ToolPanel

if TYPE_CHECKING:
    from codecrew.ui.app import ChatApp


@dataclass
class EventHandler:
    """Handles orchestrator events and updates UI components.

    Maps each EventType to appropriate UI updates for:
    - Message list (new messages, streaming)
    - Status bar (thinking, streaming, idle)
    - Tool panel (tool calls, results)
    """

    message_list: MessageList
    status_bar: StatusBar
    tool_panel: ToolPanel

    # Optional callbacks
    on_permission_request: Optional[Callable] = None
    on_error: Optional[Callable[[str], None]] = None
    on_turn_complete: Optional[Callable] = None

    async def handle(self, event: OrchestratorEvent) -> None:
        """Handle an orchestrator event.

        Args:
            event: The event to handle
        """
        handlers = {
            EventType.THINKING: self._handle_thinking,
            EventType.EVALUATING: self._handle_evaluating,
            EventType.WILL_SPEAK: self._handle_will_speak,
            EventType.WILL_STAY_SILENT: self._handle_will_stay_silent,
            EventType.RESPONSE_START: self._handle_response_start,
            EventType.RESPONSE_CHUNK: self._handle_response_chunk,
            EventType.RESPONSE_COMPLETE: self._handle_response_complete,
            EventType.TOOL_CALL: self._handle_tool_call,
            EventType.TOOL_EXECUTING: self._handle_tool_executing,
            EventType.TOOL_RESULT: self._handle_tool_result,
            EventType.TOOL_PERMISSION_REQUEST: self._handle_permission_request,
            EventType.ERROR: self._handle_error,
            EventType.TURN_COMPLETE: self._handle_turn_complete,
        }

        handler = handlers.get(event.type)
        if handler:
            await handler(event)

    async def _handle_thinking(self, event: OrchestratorEvent) -> None:
        """Handle THINKING event - models are being evaluated."""
        self.status_bar.set_status("thinking")
        # Note: We don't have the model list here, so we just update status
        # The thinking indicator will be started by the app when it has the model list

    async def _handle_evaluating(self, event: OrchestratorEvent) -> None:
        """Handle EVALUATING event - a specific model is being evaluated."""
        if event.model:
            self.status_bar.set_status("thinking", model=event.model)

    async def _handle_will_speak(self, event: OrchestratorEvent) -> None:
        """Handle WILL_SPEAK event - model decided to speak."""
        if event.decision:
            self.message_list.add_decision(
                model=event.decision.model,
                will_speak=True,
                confidence=event.decision.confidence,
                reason=event.decision.reason,
                is_forced=event.decision.is_forced,
            )

    async def _handle_will_stay_silent(self, event: OrchestratorEvent) -> None:
        """Handle WILL_STAY_SILENT event - model decided not to speak."""
        if event.decision:
            self.message_list.add_decision(
                model=event.decision.model,
                will_speak=False,
                confidence=event.decision.confidence,
                reason=event.decision.reason,
                is_forced=event.decision.is_forced,
            )

    async def _handle_response_start(self, event: OrchestratorEvent) -> None:
        """Handle RESPONSE_START event - model starting to generate."""
        if event.model:
            self.message_list.stop_thinking()
            self.message_list.start_typing(event.model)
            self.status_bar.set_status("streaming", model=event.model)

    async def _handle_response_chunk(self, event: OrchestratorEvent) -> None:
        """Handle RESPONSE_CHUNK event - streaming chunk received."""
        if event.model and event.content:
            # Check if we have an active streaming message
            if not self.message_list.is_streaming:
                self.message_list.stop_typing()
                self.message_list.start_streaming(event.model)

            # Append the chunk
            if self.message_list._streaming:
                self.message_list._streaming.append(event.content)

    async def _handle_response_complete(self, event: OrchestratorEvent) -> None:
        """Handle RESPONSE_COMPLETE event - full response ready."""
        if event.response:
            self.message_list.stop_typing()
            self.message_list.finish_streaming(event.response)

            # Update status bar with usage
            if event.response.usage:
                self.status_bar.update_usage(event.response.usage)

            self.status_bar.set_status("idle")

    async def _handle_tool_call(self, event: OrchestratorEvent) -> None:
        """Handle TOOL_CALL event - model wants to call a tool."""
        if event.tool_call and event.model:
            # Add to message list
            self.message_list.add_tool_call(event.tool_call, event.model)

            # Add to tool panel
            self.tool_panel.add_call(event.tool_call, event.model)

    async def _handle_tool_executing(self, event: OrchestratorEvent) -> None:
        """Handle TOOL_EXECUTING event - tool is being executed."""
        if event.tool_call and event.model:
            self.message_list.start_tool_executing(
                event.tool_call.name,
                event.model,
            )
            self.status_bar.set_status(
                "thinking",
                message=f"Executing {event.tool_call.name}",
            )

            # Update tool panel
            display = self.tool_panel.get_call(event.tool_call.id)
            if display:
                display.set_executing()

    async def _handle_tool_result(self, event: OrchestratorEvent) -> None:
        """Handle TOOL_RESULT event - tool execution completed."""
        if event.tool_result:
            self.message_list.stop_tool_executing()
            self.message_list.add_tool_result(event.tool_result)

            # Update tool panel
            self.tool_panel.update_call(
                event.tool_result.tool_call_id,
                event.tool_result,
            )

            self.status_bar.set_status("idle")

    async def _handle_permission_request(self, event: OrchestratorEvent) -> None:
        """Handle TOOL_PERMISSION_REQUEST event - tool requires permission."""
        if self.on_permission_request and event.tool_call and event.permission_request:
            await self.on_permission_request(
                event.model,
                event.tool_call,
                event.permission_request,
            )

    async def _handle_error(self, event: OrchestratorEvent) -> None:
        """Handle ERROR event - an error occurred."""
        if event.error:
            self.message_list.clear_indicators()
            self.message_list.add_error(event.error, event.model)
            self.status_bar.set_status("error", message=event.error)

            if self.on_error:
                self.on_error(event.error)

    async def _handle_turn_complete(self, event: OrchestratorEvent) -> None:
        """Handle TURN_COMPLETE event - all models done for this turn."""
        self.message_list.clear_indicators()
        self.status_bar.set_status("idle")

        # Update total usage
        if event.usage:
            self.status_bar.update_usage(event.usage)

        self.status_bar.mark_modified()

        if self.on_turn_complete:
            await self.on_turn_complete()


class StreamingEventBuffer:
    """Buffers streaming events for smooth UI updates.

    Aggregates rapid RESPONSE_CHUNK events to reduce
    UI update frequency while maintaining responsiveness.
    """

    def __init__(self, flush_interval: float = 0.05):
        """Initialize the buffer.

        Args:
            flush_interval: Minimum time between UI updates in seconds
        """
        self.flush_interval = flush_interval
        self._buffer: dict[str, str] = {}  # model -> accumulated content
        self._last_flush: float = 0.0

    def add_chunk(self, model: str, content: str) -> None:
        """Add a chunk to the buffer.

        Args:
            model: Model name
            content: Content chunk
        """
        if model not in self._buffer:
            self._buffer[model] = ""
        self._buffer[model] += content

    def should_flush(self, current_time: float) -> bool:
        """Check if buffer should be flushed.

        Args:
            current_time: Current time in seconds

        Returns:
            True if flush is needed
        """
        return current_time - self._last_flush >= self.flush_interval

    def flush(self, current_time: float) -> dict[str, str]:
        """Flush the buffer and return accumulated content.

        Args:
            current_time: Current time in seconds

        Returns:
            Dictionary of model -> accumulated content
        """
        result = dict(self._buffer)
        self._buffer.clear()
        self._last_flush = current_time
        return result

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
