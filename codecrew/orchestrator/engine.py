"""Main orchestration engine for CodeCrew.

The Orchestrator coordinates multi-model conversations by:
1. Parsing @mentions from user messages
2. Evaluating which models should speak
3. Generating responses sequentially
4. Handling tool calls and errors
5. Yielding events for UI rendering
"""

import asyncio
import logging
from typing import AsyncIterator, Optional, Set

from codecrew.config import Settings
from codecrew.models.base import ModelClient, ModelError
from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    StreamChunk,
    ToolCall,
    ToolResult,
    Usage,
)

from .context import ContextAssembler
from .events import EventType, OrchestratorEvent, SpeakerDecision
from .mentions import ParsedMentions, get_forced_speakers, parse_mentions
from .speaking import SpeakingEvaluator
from .turns import TurnManager, TurnStrategy

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestration engine for multi-model conversations.

    Coordinates the full lifecycle of processing user messages:
    - Parsing mentions
    - Evaluating speaker intentions
    - Generating responses
    - Handling tool calls
    - Managing conversation state
    """

    def __init__(
        self,
        clients: dict[str, ModelClient],
        settings: Settings,
        turn_strategy: TurnStrategy = "rotate",
    ):
        """Initialize the orchestrator.

        Args:
            clients: Dictionary of model name to client
            settings: Application settings
            turn_strategy: Strategy for turn ordering
        """
        self.clients = clients
        self.settings = settings

        # Get available model names
        self.available_models = [
            name for name, client in clients.items()
            if client.is_available
        ]

        # Initialize components
        self.speaking_evaluator = SpeakingEvaluator(
            clients={k: v for k, v in clients.items() if v.is_available},
            silence_threshold=settings.conversation.silence_threshold,
        )

        self.turn_manager = TurnManager(
            strategy=turn_strategy,
            fixed_order=self.available_models,
        )

        self.context_assembler = ContextAssembler(
            max_tokens=settings.conversation.max_context_tokens,
        )

        # Conversation state (can be set externally)
        self._conversation: list[Message] = []
        self._pinned_ids: Set[str] = set()

    @property
    def conversation(self) -> list[Message]:
        """Get the current conversation history."""
        return self._conversation

    @conversation.setter
    def conversation(self, messages: list[Message]) -> None:
        """Set the conversation history."""
        self._conversation = messages

    @property
    def pinned_ids(self) -> Set[str]:
        """Get the set of pinned message IDs."""
        return self._pinned_ids

    def pin_message(self, message_id: str) -> None:
        """Pin a message to always include in context."""
        self._pinned_ids.add(message_id)

    def unpin_message(self, message_id: str) -> None:
        """Unpin a message."""
        self._pinned_ids.discard(message_id)

    def add_message(self, message: Message) -> None:
        """Add a message to conversation history."""
        self._conversation.append(message)

    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        self._conversation.clear()
        self._pinned_ids.clear()

    async def process_message(
        self,
        user_message: str,
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Process a user message and generate model responses.

        This is the main entry point for the orchestration flow.

        Args:
            user_message: The user's message (may contain @mentions)
            stream: Whether to stream responses

        Yields:
            OrchestratorEvent objects for UI rendering
        """
        # 1. Parse @mentions
        parsed = parse_mentions(user_message)
        forced_speakers = get_forced_speakers(parsed, self.available_models)

        # 2. Add user message to conversation
        user_msg = Message.user(parsed.clean_message)
        self.add_message(user_msg)

        # 3. Evaluate who should speak
        yield OrchestratorEvent.thinking()

        decisions = await self.speaking_evaluator.evaluate_all(
            conversation=self._conversation,
            user_message=parsed.clean_message,
            forced_speakers=forced_speakers,
        )

        # 4. Emit speaking intention events
        for decision in decisions:
            if decision.should_speak:
                yield OrchestratorEvent.will_speak(decision)
            else:
                yield OrchestratorEvent.will_stay_silent(decision)

        # 5. Determine speaking order
        speaking_order = self.turn_manager.determine_order(decisions)

        if not speaking_order:
            # All models stayed silent
            logger.info("All models chose to stay silent")
            yield OrchestratorEvent.turn_complete(responses=[], usage=None)
            return

        # 6. Generate responses sequentially
        responses: list[ModelResponse] = []
        total_usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        for model_name in speaking_order:
            async for event in self._generate_model_response(
                model_name=model_name,
                previous_responses=responses,
                stream=stream,
            ):
                yield event

                # Collect completed responses
                if event.type == EventType.RESPONSE_COMPLETE and event.response:
                    responses.append(event.response)

                    # Accumulate usage
                    if event.response.usage:
                        total_usage = total_usage + event.response.usage

        # 7. Complete the turn
        yield OrchestratorEvent.turn_complete(
            responses=responses,
            usage=total_usage if total_usage.total_tokens > 0 else None,
        )

    async def _generate_model_response(
        self,
        model_name: str,
        previous_responses: list[ModelResponse],
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Generate a response from a single model.

        Args:
            model_name: Name of the model to generate from
            previous_responses: Responses already generated this turn
            stream: Whether to stream the response

        Yields:
            OrchestratorEvent objects for this model's response
        """
        client = self.clients.get(model_name)
        if not client or not client.is_available:
            yield OrchestratorEvent.error_event(
                f"Model {model_name} is not available",
                model=model_name,
            )
            return

        # Emit response start
        yield OrchestratorEvent.response_start(model_name)

        try:
            # Assemble context for this model
            other_models = [m for m in self.available_models if m != model_name]

            # Add context about previous responses this turn
            additional_context = None
            if previous_responses:
                prev_summary = "\n".join(
                    f"- {r.model}: {r.content[:200]}..."
                    if len(r.content) > 200 else f"- {r.model}: {r.content}"
                    for r in previous_responses
                )
                additional_context = f"Other models have already responded this turn:\n{prev_summary}"

            system_prompt, context_messages = self.context_assembler.assemble_for_model(
                conversation=self._conversation,
                model=client,
                other_models=other_models,
                pinned_ids=self._pinned_ids,
                additional_context=additional_context,
            )

            if stream:
                async for event in self._stream_response(
                    client=client,
                    model_name=model_name,
                    messages=context_messages,
                    system=system_prompt,
                ):
                    yield event
            else:
                async for event in self._generate_response(
                    client=client,
                    model_name=model_name,
                    messages=context_messages,
                    system=system_prompt,
                ):
                    yield event

        except ModelError as e:
            logger.error(f"Model error from {model_name}: {e}")
            yield OrchestratorEvent.error_event(str(e), model=model_name)

        except Exception as e:
            logger.exception(f"Unexpected error from {model_name}")
            yield OrchestratorEvent.error_event(
                f"Unexpected error: {e}",
                model=model_name,
            )

    async def _stream_response(
        self,
        client: ModelClient,
        model_name: str,
        messages: list[Message],
        system: Optional[str],
    ) -> AsyncIterator[OrchestratorEvent]:
        """Stream a response from a model.

        Args:
            client: Model client
            model_name: Model name
            messages: Context messages
            system: System prompt

        Yields:
            OrchestratorEvent objects
        """
        content_buffer = ""
        tool_calls: list[ToolCall] = []
        finish_reason = FinishReason.STOP
        usage: Optional[Usage] = None

        async for chunk in client.generate_stream(
            messages=messages,
            system=system,
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

        # Build complete response
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

        yield OrchestratorEvent.response_complete(model_name, response)

    async def _generate_response(
        self,
        client: ModelClient,
        model_name: str,
        messages: list[Message],
        system: Optional[str],
    ) -> AsyncIterator[OrchestratorEvent]:
        """Generate a non-streaming response from a model.

        Args:
            client: Model client
            model_name: Model name
            messages: Context messages
            system: System prompt

        Yields:
            OrchestratorEvent objects
        """
        response = await client.generate(
            messages=messages,
            system=system,
        )

        # Add assistant message to conversation
        assistant_msg = Message.assistant(response.content, model=model_name)
        assistant_msg.tool_calls = response.tool_calls
        self.add_message(assistant_msg)

        # Emit content as single chunk
        if response.content:
            yield OrchestratorEvent.response_chunk(model_name, response.content)

        # Emit tool calls
        for tc in response.tool_calls:
            yield OrchestratorEvent.tool_call_event(model_name, tc)

        yield OrchestratorEvent.response_complete(model_name, response)

    async def retry_model(
        self,
        model_name: str,
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Retry generating a response from a specific model.

        Useful when a model's response was unsatisfactory or errored.

        Args:
            model_name: Model to retry
            stream: Whether to stream the response

        Yields:
            OrchestratorEvent objects
        """
        async for event in self._generate_model_response(
            model_name=model_name,
            previous_responses=[],
            stream=stream,
        ):
            yield event

    async def force_speak(
        self,
        model_name: str,
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Force a specific model to speak.

        Args:
            model_name: Model to force
            stream: Whether to stream

        Yields:
            OrchestratorEvent objects
        """
        # Emit forced speaking decision
        decision = SpeakerDecision.forced(model_name)
        yield OrchestratorEvent.will_speak(decision)

        async for event in self._generate_model_response(
            model_name=model_name,
            previous_responses=[],
            stream=stream,
        ):
            yield event

    def get_model_status(self) -> dict[str, dict]:
        """Get status information for all models.

        Returns:
            Dictionary of model name to status info
        """
        return {
            name: {
                "available": client.is_available,
                "display_name": client.display_name,
                "color": client.color,
                "model_id": client.model_id,
            }
            for name, client in self.clients.items()
        }


def create_orchestrator(
    clients: dict[str, ModelClient],
    settings: Settings,
) -> Orchestrator:
    """Factory function to create an orchestrator.

    Args:
        clients: Model clients
        settings: Application settings

    Returns:
        Configured Orchestrator instance
    """
    # Determine turn strategy from settings
    strategy = settings.conversation.first_responder
    if strategy not in ("rotate", "confidence", "fixed"):
        strategy = "rotate"

    return Orchestrator(
        clients=clients,
        settings=settings,
        turn_strategy=strategy,  # type: ignore
    )
