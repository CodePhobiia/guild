"""Persistent orchestrator with automatic conversation management.

Wraps the base Orchestrator with ConversationManager integration to provide:
- Automatic message persistence
- Session management
- Conversation history restoration
- Summarization triggers
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional, Set

from codecrew.config import Settings
from codecrew.models.base import ModelClient
from codecrew.models.types import Message, Usage

from .context import ContextAssembler
from .engine import Orchestrator
from .events import EventType, OrchestratorEvent
from .turns import TurnStrategy

if TYPE_CHECKING:
    from codecrew.conversation.manager import ConversationManager
    from codecrew.conversation.summarizer import SummaryManager

logger = logging.getLogger(__name__)


class PersistentOrchestrator:
    """Orchestrator with automatic persistence and session management.

    Wraps the base Orchestrator to provide:
    - Automatic message persistence to SQLite
    - Session lifecycle management
    - Conversation history restoration on startup
    - Automatic summarization when token thresholds are exceeded
    """

    def __init__(
        self,
        clients: dict[str, ModelClient],
        settings: Settings,
        conversation_manager: "ConversationManager",
        turn_strategy: TurnStrategy = "rotate",
        summary_manager: Optional["SummaryManager"] = None,
    ):
        """Initialize the persistent orchestrator.

        Args:
            clients: Dictionary of model name to client
            settings: Application settings
            conversation_manager: Manager for conversation persistence
            turn_strategy: Strategy for turn ordering
            summary_manager: Optional manager for automatic summarization
        """
        self._orchestrator = Orchestrator(
            clients=clients,
            settings=settings,
            turn_strategy=turn_strategy,
        )

        self._conversation_manager = conversation_manager
        self._summary_manager = summary_manager
        self._settings = settings

        # Track pending messages for batch persistence
        self._pending_messages: list[tuple[Message, Optional[Usage]]] = []

    @property
    def orchestrator(self) -> Orchestrator:
        """Get the underlying orchestrator."""
        return self._orchestrator

    @property
    def conversation_manager(self) -> "ConversationManager":
        """Get the conversation manager."""
        return self._conversation_manager

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._conversation_manager.current_session_id

    @property
    def has_session(self) -> bool:
        """Check if a session is active."""
        return self._conversation_manager.has_active_session

    @property
    def available_models(self) -> list[str]:
        """Get list of available model names."""
        return self._orchestrator.available_models

    @property
    def conversation(self) -> list[Message]:
        """Get the current conversation history."""
        return self._orchestrator.conversation

    @property
    def pinned_ids(self) -> Set[str]:
        """Get pinned message IDs."""
        return self._orchestrator.pinned_ids

    # ========== Session Management ==========

    async def create_session(
        self,
        name: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> str:
        """Create a new session.

        Args:
            name: Optional session name
            project_path: Optional project path

        Returns:
            New session ID
        """
        session = await self._conversation_manager.create_session(
            name=name,
            project_path=project_path,
        )

        # Clear orchestrator state for new session
        self._orchestrator.clear_conversation()
        self._pending_messages.clear()

        logger.info(f"Created session: {session.id}")
        return session.id

    async def load_session(self, session_id: str) -> None:
        """Load an existing session and restore conversation state.

        Args:
            session_id: Session ID to load
        """
        session = await self._conversation_manager.load_session(session_id)

        # Restore messages to orchestrator
        messages = await self._conversation_manager.load_as_orchestrator_messages()
        self._orchestrator.conversation = messages

        # Restore pinned IDs
        for pin_id in self._conversation_manager.pinned_ids:
            self._orchestrator.pin_message(pin_id)

        self._pending_messages.clear()

        logger.info(f"Loaded session: {session_id} ({len(messages)} messages)")

    async def ensure_session(
        self,
        name: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> str:
        """Ensure a session exists, creating one if needed.

        Args:
            name: Session name if creating
            project_path: Project path if creating

        Returns:
            Session ID
        """
        if self.has_session:
            return self.session_id  # type: ignore

        return await self.create_session(name=name, project_path=project_path)

    # ========== Message Processing ==========

    async def process_message(
        self,
        user_message: str,
        stream: bool = True,
        auto_persist: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Process a user message with automatic persistence.

        Args:
            user_message: The user's message
            stream: Whether to stream responses
            auto_persist: Whether to persist messages automatically

        Yields:
            OrchestratorEvent objects
        """
        # Ensure we have a session
        await self.ensure_session()

        # Track conversation length before processing
        initial_length = len(self._orchestrator.conversation)

        # Process through base orchestrator
        async for event in self._orchestrator.process_message(user_message, stream=stream):
            yield event

            # Track responses for persistence
            if event.type == EventType.RESPONSE_COMPLETE and event.response:
                # The orchestrator already added the message
                pass

            elif event.type == EventType.TURN_COMPLETE:
                # Persist new messages
                if auto_persist:
                    await self._persist_new_messages(initial_length, event.usage)

                # Check for summarization trigger
                if self._summary_manager and self._summary_manager.is_enabled:
                    await self._check_summarization()

    async def _persist_new_messages(
        self,
        initial_length: int,
        turn_usage: Optional[Usage],
    ) -> None:
        """Persist new messages added during processing.

        Args:
            initial_length: Conversation length before processing
            turn_usage: Usage info for the turn
        """
        new_messages = self._orchestrator.conversation[initial_length:]

        if not new_messages:
            return

        for i, msg in enumerate(new_messages):
            # Calculate per-message usage (approximate for multi-model turns)
            msg_usage = None
            if turn_usage and len(new_messages) > 0:
                # Distribute usage roughly among messages
                if i == 0:
                    # User message - no completion tokens
                    msg_usage = Usage(
                        prompt_tokens=turn_usage.prompt_tokens // len(new_messages),
                        completion_tokens=0,
                        total_tokens=turn_usage.prompt_tokens // len(new_messages),
                    )
                else:
                    # Assistant message
                    per_msg_completion = turn_usage.completion_tokens // (len(new_messages) - 1) if len(new_messages) > 1 else 0
                    msg_usage = Usage(
                        prompt_tokens=0,
                        completion_tokens=per_msg_completion,
                        total_tokens=per_msg_completion,
                        cost_estimate=turn_usage.cost_estimate / (len(new_messages) - 1) if turn_usage.cost_estimate and len(new_messages) > 1 else None,
                    )

            await self._conversation_manager.persist_message(msg, usage=msg_usage)

        logger.debug(f"Persisted {len(new_messages)} new messages")

    async def _check_summarization(self) -> None:
        """Check if summarization is needed and trigger if so."""
        if not self._summary_manager:
            return

        # Get a token counter (use first available client)
        token_counter = None
        for client in self._orchestrator.clients.values():
            if client.is_available:
                token_counter = client
                break

        if not token_counter:
            return

        summary = await self._summary_manager.check_and_summarize(
            session_id=self.session_id,  # type: ignore
            messages=self._orchestrator.conversation,
            token_counter=token_counter,
        )

        if summary:
            logger.info(f"Generated summary: {summary.id}")

    # ========== Pin Management ==========

    async def pin_message(self, message_id: str) -> bool:
        """Pin a message.

        Args:
            message_id: Message to pin

        Returns:
            True if pinned
        """
        # Update orchestrator
        self._orchestrator.pin_message(message_id)

        # Persist to database
        return await self._conversation_manager.pin_message(message_id)

    async def unpin_message(self, message_id: str) -> bool:
        """Unpin a message.

        Args:
            message_id: Message to unpin

        Returns:
            True if unpinned
        """
        # Update orchestrator
        self._orchestrator.unpin_message(message_id)

        # Persist to database
        return await self._conversation_manager.unpin_message(message_id)

    # ========== Model Operations ==========

    async def retry_model(
        self,
        model_name: str,
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Retry generating a response from a specific model.

        Args:
            model_name: Model to retry
            stream: Whether to stream

        Yields:
            OrchestratorEvent objects
        """
        initial_length = len(self._orchestrator.conversation)

        async for event in self._orchestrator.retry_model(model_name, stream=stream):
            yield event

            if event.type == EventType.RESPONSE_COMPLETE:
                # Persist the new response
                new_messages = self._orchestrator.conversation[initial_length:]
                for msg in new_messages:
                    await self._conversation_manager.persist_message(msg)

    async def force_speak(
        self,
        model_name: str,
        stream: bool = True,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Force a model to speak.

        Args:
            model_name: Model to force
            stream: Whether to stream

        Yields:
            OrchestratorEvent objects
        """
        initial_length = len(self._orchestrator.conversation)

        async for event in self._orchestrator.force_speak(model_name, stream=stream):
            yield event

            if event.type == EventType.RESPONSE_COMPLETE:
                new_messages = self._orchestrator.conversation[initial_length:]
                for msg in new_messages:
                    await self._conversation_manager.persist_message(msg)

    # ========== Utility Methods ==========

    def get_model_status(self) -> dict[str, dict]:
        """Get status information for all models."""
        return self._orchestrator.get_model_status()

    async def get_stats(self) -> dict:
        """Get conversation statistics."""
        return await self._conversation_manager.get_conversation_stats()

    async def export(self, format: str = "json") -> str:
        """Export the current session.

        Args:
            format: Export format ('json' or 'markdown')

        Returns:
            Exported content
        """
        return await self._conversation_manager.export_session(format=format)

    async def clear_conversation(self) -> None:
        """Clear the current conversation (in-memory only)."""
        self._orchestrator.clear_conversation()
        self._pending_messages.clear()


async def create_persistent_orchestrator(
    clients: dict[str, ModelClient],
    settings: Settings,
    db_path: str,
    turn_strategy: TurnStrategy = "rotate",
    enable_summarization: bool = True,
    summarizer_client: Optional[ModelClient] = None,
) -> PersistentOrchestrator:
    """Factory function to create a PersistentOrchestrator.

    Args:
        clients: Model clients
        settings: Application settings
        db_path: Path to SQLite database
        turn_strategy: Turn ordering strategy
        enable_summarization: Whether to enable auto-summarization
        summarizer_client: Client to use for summarization

    Returns:
        Configured PersistentOrchestrator
    """
    from codecrew.conversation import create_conversation_manager

    # Create conversation manager
    conversation_manager = await create_conversation_manager(db_path)

    # Create summary manager if enabled
    summary_manager = None
    if enable_summarization:
        from codecrew.conversation import SummaryManager

        # Use provided client or first available
        client = summarizer_client
        if not client:
            for c in clients.values():
                if c.is_available:
                    client = c
                    break

        if client:
            summary_manager = SummaryManager(
                db=conversation_manager.db,
                summarizer_client=client,
            )

    return PersistentOrchestrator(
        clients=clients,
        settings=settings,
        conversation_manager=conversation_manager,
        turn_strategy=turn_strategy,
        summary_manager=summary_manager,
    )
