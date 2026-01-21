"""High-level conversation management for CodeCrew.

The ConversationManager bridges the gap between:
- Orchestrator (in-memory Message objects from models/types.py)
- DatabaseManager (persistent storage in SQLite)
- ContextAssembler (context window building)

It provides:
- Session lifecycle management (create, load, switch, archive)
- Automatic persistence of messages during conversation
- Bidirectional pin synchronization
- Conversation statistics and analytics
- Context summarization trigger
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Optional, Set

from codecrew.models.base import ModelClient
from codecrew.models.types import Message as OrchestratorMessage
from codecrew.models.types import MessageRole, ToolCall as OrchestratorToolCall, Usage

from .models import Message as PersistentMessage
from .models import MessageRole as PersistentMessageRole
from .models import Session, ToolCall as PersistentToolCall, ToolCallStatus
from .persistence import DatabaseManager

logger = logging.getLogger(__name__)


class ConversationManager:
    """High-level interface for managing conversations with persistence.

    Coordinates between in-memory orchestration and persistent storage,
    providing session lifecycle management and automatic message saving.
    """

    def __init__(
        self,
        db: DatabaseManager,
        auto_persist: bool = True,
    ):
        """Initialize the conversation manager.

        Args:
            db: Database manager for persistence
            auto_persist: Whether to automatically persist messages
        """
        self.db = db
        self.auto_persist = auto_persist

        # Current session state
        self._current_session_id: Optional[str] = None
        self._pinned_ids: Set[str] = set()

        # Message ID mapping (orchestrator messages don't have IDs)
        self._message_id_map: dict[int, str] = {}  # id(message) -> db_id

        # Callbacks for events
        self._on_message_persisted: Optional[Callable[[str], None]] = None

    @property
    def current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session_id

    @property
    def has_active_session(self) -> bool:
        """Check if there is an active session."""
        return self._current_session_id is not None

    @property
    def pinned_ids(self) -> Set[str]:
        """Get the set of pinned message IDs."""
        return self._pinned_ids.copy()

    # ========== Session Lifecycle ==========

    async def create_session(
        self,
        name: Optional[str] = None,
        project_path: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Session:
        """Create a new conversation session.

        Args:
            name: Optional session name
            project_path: Optional project path
            metadata: Optional metadata dictionary

        Returns:
            Created Session object
        """
        session_id = str(uuid.uuid4())

        row = await self.db.create_session(
            session_id=session_id,
            name=name,
            project_path=project_path,
            metadata=metadata,
        )

        self._current_session_id = session_id
        self._pinned_ids.clear()
        self._message_id_map.clear()

        logger.info(f"Created session: {session_id}")

        return Session.from_db_row(row)

    async def load_session(self, session_id: str) -> Session:
        """Load an existing session and its messages.

        Args:
            session_id: Session ID to load

        Returns:
            Loaded Session with messages

        Raises:
            ValueError: If session not found
        """
        row = await self.db.get_session(session_id)
        if not row:
            raise ValueError(f"Session not found: {session_id}")

        # Load messages
        message_rows = await self.db.get_session_messages(session_id)
        messages = []

        for msg_row in message_rows:
            tool_calls = await self.db.get_message_tool_calls(msg_row["id"])
            messages.append(PersistentMessage.from_db_row(msg_row, tool_calls))

        # Load pinned messages
        pinned_rows = await self.db.get_pinned_messages(session_id)
        self._pinned_ids = {row["id"] for row in pinned_rows}

        self._current_session_id = session_id
        self._message_id_map.clear()

        logger.info(f"Loaded session: {session_id} ({len(messages)} messages)")

        return Session.from_db_row(row, messages)

    async def switch_session(self, session_id: str) -> Session:
        """Switch to a different session.

        Args:
            session_id: Session ID to switch to

        Returns:
            Loaded Session
        """
        return await self.load_session(session_id)

    async def get_current_session(self) -> Optional[Session]:
        """Get the current session if active.

        Returns:
            Current Session or None
        """
        if not self._current_session_id:
            return None

        return await self.load_session(self._current_session_id)

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Session]:
        """List all sessions, most recent first.

        Args:
            limit: Maximum sessions to return
            offset: Number of sessions to skip

        Returns:
            List of Session objects (without messages)
        """
        rows = await self.db.list_sessions(limit=limit, offset=offset)
        return [Session.from_db_row(row) for row in rows]

    async def search_sessions(self, query: str) -> list[Session]:
        """Search sessions by name or content.

        Args:
            query: Search query

        Returns:
            Matching sessions
        """
        rows = await self.db.search_sessions(query)
        return [Session.from_db_row(row) for row in rows]

    async def update_session(
        self,
        name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Session]:
        """Update the current session.

        Args:
            name: New session name
            metadata: New metadata

        Returns:
            Updated Session or None if no active session
        """
        if not self._current_session_id:
            return None

        row = await self.db.update_session(
            session_id=self._current_session_id,
            name=name,
            metadata=metadata,
        )

        if row:
            return Session.from_db_row(row)
        return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted
        """
        success = await self.db.delete_session(session_id)

        if success and session_id == self._current_session_id:
            self._current_session_id = None
            self._pinned_ids.clear()
            self._message_id_map.clear()

        return success

    async def archive_session(self, session_id: Optional[str] = None) -> bool:
        """Archive a session by adding archived metadata.

        Args:
            session_id: Session to archive (or current if None)

        Returns:
            True if archived
        """
        target_id = session_id or self._current_session_id
        if not target_id:
            return False

        session_row = await self.db.get_session(target_id)
        if not session_row:
            return False

        existing_metadata = json.loads(session_row["metadata"]) if session_row["metadata"] else {}
        existing_metadata["archived"] = True
        existing_metadata["archived_at"] = datetime.utcnow().isoformat()

        await self.db.update_session(target_id, metadata=existing_metadata)

        if target_id == self._current_session_id:
            self._current_session_id = None
            self._pinned_ids.clear()

        return True

    # ========== Message Operations ==========

    async def persist_message(
        self,
        message: OrchestratorMessage,
        usage: Optional[Usage] = None,
    ) -> str:
        """Persist an orchestrator message to the database.

        Args:
            message: Orchestrator Message to persist
            usage: Optional usage information

        Returns:
            Database message ID
        """
        if not self._current_session_id:
            raise ValueError("No active session")

        message_id = str(uuid.uuid4())

        # Map orchestrator role to persistent role
        role = message.role.value

        # Extract usage info
        tokens_used = usage.total_tokens if usage else None
        cost_estimate = usage.cost_estimate if usage else None

        await self.db.add_message(
            message_id=message_id,
            session_id=self._current_session_id,
            role=role,
            content=message.content,
            model=message.model,
            tokens_used=tokens_used,
            cost_estimate=cost_estimate,
        )

        # Persist tool calls
        for tc in message.tool_calls:
            await self.db.add_tool_call(
                tool_call_id=tc.id,
                message_id=message_id,
                tool_name=tc.name,
                parameters=tc.arguments,
                status="pending",
            )

        # Store mapping
        self._message_id_map[id(message)] = message_id

        logger.debug(f"Persisted message: {message_id}")

        if self._on_message_persisted:
            self._on_message_persisted(message_id)

        return message_id

    async def persist_messages(
        self,
        messages: list[OrchestratorMessage],
    ) -> list[str]:
        """Persist multiple messages in a batch.

        Args:
            messages: Messages to persist

        Returns:
            List of database message IDs
        """
        message_ids = []
        for msg in messages:
            msg_id = await self.persist_message(msg)
            message_ids.append(msg_id)
        return message_ids

    async def get_message(self, message_id: str) -> Optional[PersistentMessage]:
        """Get a message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message or None
        """
        row = await self.db.get_message(message_id)
        if not row:
            return None

        tool_calls = await self.db.get_message_tool_calls(message_id)
        return PersistentMessage.from_db_row(row, tool_calls)

    async def get_conversation_messages(
        self,
        limit: Optional[int] = None,
    ) -> list[PersistentMessage]:
        """Get messages for the current session.

        Args:
            limit: Maximum messages to return

        Returns:
            List of messages in chronological order
        """
        if not self._current_session_id:
            return []

        rows = await self.db.get_session_messages(self._current_session_id, limit=limit)
        messages = []

        for row in rows:
            tool_calls = await self.db.get_message_tool_calls(row["id"])
            messages.append(PersistentMessage.from_db_row(row, tool_calls))

        return messages

    async def load_as_orchestrator_messages(
        self,
        limit: Optional[int] = None,
    ) -> list[OrchestratorMessage]:
        """Load session messages as orchestrator Message objects.

        Useful for restoring conversation state to an Orchestrator.

        Args:
            limit: Maximum messages to return

        Returns:
            List of orchestrator Message objects
        """
        persistent_messages = await self.get_conversation_messages(limit=limit)

        orchestrator_messages = []
        for pm in persistent_messages:
            om = self._to_orchestrator_message(pm)
            orchestrator_messages.append(om)
            # Store the reverse mapping
            self._message_id_map[id(om)] = pm.id

        return orchestrator_messages

    def _to_orchestrator_message(self, pm: PersistentMessage) -> OrchestratorMessage:
        """Convert a persistent message to an orchestrator message.

        Args:
            pm: Persistent message

        Returns:
            Orchestrator message
        """
        # Convert tool calls
        tool_calls = [
            OrchestratorToolCall(
                id=tc.id,
                name=tc.tool_name,
                arguments=tc.parameters or {},
            )
            for tc in pm.tool_calls
        ]

        return OrchestratorMessage(
            role=MessageRole(pm.role.value),
            content=pm.content,
            model=pm.model,
            tool_calls=tool_calls,
        )

    def get_message_id(self, message: OrchestratorMessage) -> Optional[str]:
        """Get the database ID for an orchestrator message.

        Args:
            message: Orchestrator message

        Returns:
            Database ID or None if not persisted
        """
        return self._message_id_map.get(id(message))

    # ========== Pin Operations ==========

    async def pin_message(self, message_id: str) -> bool:
        """Pin a message to always include in context.

        Args:
            message_id: Message to pin

        Returns:
            True if pinned successfully
        """
        if not self._current_session_id:
            return False

        pin_id = str(uuid.uuid4())
        await self.db.pin_message(self._current_session_id, message_id, pin_id)
        self._pinned_ids.add(message_id)

        logger.debug(f"Pinned message: {message_id}")
        return True

    async def unpin_message(self, message_id: str) -> bool:
        """Unpin a message.

        Args:
            message_id: Message to unpin

        Returns:
            True if unpinned
        """
        await self.db.unpin_message(message_id)
        self._pinned_ids.discard(message_id)

        logger.debug(f"Unpinned message: {message_id}")
        return True

    async def get_pinned_messages(self) -> list[PersistentMessage]:
        """Get all pinned messages for the current session.

        Returns:
            List of pinned messages
        """
        if not self._current_session_id:
            return []

        rows = await self.db.get_pinned_messages(self._current_session_id)
        messages = []

        for row in rows:
            tool_calls = await self.db.get_message_tool_calls(row["id"])
            messages.append(PersistentMessage.from_db_row(row, tool_calls))

        return messages

    async def sync_pins_from_db(self) -> Set[str]:
        """Sync pinned IDs from database to memory.

        Returns:
            Set of pinned message IDs
        """
        if not self._current_session_id:
            return set()

        rows = await self.db.get_pinned_messages(self._current_session_id)
        self._pinned_ids = {row["id"] for row in rows}
        return self._pinned_ids

    # ========== Tool Call Operations ==========

    async def update_tool_call(
        self,
        tool_call_id: str,
        result: Optional[dict[str, Any]] = None,
        status: str = "success",
    ) -> bool:
        """Update a tool call with its result.

        Args:
            tool_call_id: Tool call to update
            result: Tool execution result
            status: New status (success/error)

        Returns:
            True if updated
        """
        row = await self.db.update_tool_call(
            tool_call_id=tool_call_id,
            result=result,
            status=status,
        )
        return row is not None

    # ========== Statistics & Analytics ==========

    async def get_conversation_stats(self) -> dict[str, Any]:
        """Get statistics for the current conversation.

        Returns:
            Dictionary with conversation statistics
        """
        if not self._current_session_id:
            return {}

        messages = await self.get_conversation_messages()

        total_messages = len(messages)
        total_tokens = sum(m.tokens_used or 0 for m in messages)
        total_cost = sum(m.cost_estimate or 0 for m in messages)

        # Count by role
        by_role = {"user": 0, "assistant": 0, "system": 0, "tool": 0}
        for m in messages:
            by_role[m.role.value] = by_role.get(m.role.value, 0) + 1

        # Count by model
        by_model: dict[str, dict[str, Any]] = {}
        for m in messages:
            if m.model:
                if m.model not in by_model:
                    by_model[m.model] = {"messages": 0, "tokens": 0, "cost": 0.0}
                by_model[m.model]["messages"] += 1
                by_model[m.model]["tokens"] += m.tokens_used or 0
                by_model[m.model]["cost"] += m.cost_estimate or 0.0

        # Get session info
        session_row = await self.db.get_session(self._current_session_id)
        duration = None
        if session_row:
            created = datetime.fromisoformat(session_row["created_at"])
            updated = datetime.fromisoformat(session_row["updated_at"])
            duration = (updated - created).total_seconds()

        return {
            "session_id": self._current_session_id,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "by_role": by_role,
            "by_model": by_model,
            "pinned_count": len(self._pinned_ids),
            "duration_seconds": duration,
        }

    async def get_model_messages(self, model_name: str) -> list[PersistentMessage]:
        """Get all messages from a specific model.

        Args:
            model_name: Model name to filter by

        Returns:
            Messages from that model
        """
        all_messages = await self.get_conversation_messages()
        return [m for m in all_messages if m.model == model_name]

    # ========== Export & Import ==========

    async def export_session(
        self,
        session_id: Optional[str] = None,
        format: str = "json",
    ) -> str:
        """Export a session to JSON or Markdown.

        Args:
            session_id: Session to export (or current)
            format: Export format ('json' or 'markdown')

        Returns:
            Exported content as string
        """
        target_id = session_id or self._current_session_id
        if not target_id:
            raise ValueError("No session to export")

        session_row = await self.db.get_session(target_id)
        if not session_row:
            raise ValueError(f"Session not found: {target_id}")

        message_rows = await self.db.get_session_messages(target_id)
        messages = []
        for row in message_rows:
            tool_calls = await self.db.get_message_tool_calls(row["id"])
            messages.append(PersistentMessage.from_db_row(row, tool_calls))

        session = Session.from_db_row(session_row, messages)

        if format == "json":
            return self._export_json(session)
        elif format == "markdown":
            return self._export_markdown(session)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _export_json(self, session: Session) -> str:
        """Export session as JSON."""
        data = {
            "id": session.id,
            "name": session.name,
            "project_path": session.project_path,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "model": m.model,
                    "tokens_used": m.tokens_used,
                    "cost_estimate": m.cost_estimate,
                    "is_pinned": m.is_pinned,
                    "created_at": m.created_at.isoformat(),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "tool_name": tc.tool_name,
                            "parameters": tc.parameters,
                            "result": tc.result,
                            "status": tc.status.value,
                        }
                        for tc in m.tool_calls
                    ],
                }
                for m in session.messages
            ],
        }
        return json.dumps(data, indent=2)

    def _export_markdown(self, session: Session) -> str:
        """Export session as Markdown."""
        lines = [
            f"# {session.display_name}",
            "",
            f"**Created:** {session.created_at.isoformat()}",
            f"**Updated:** {session.updated_at.isoformat()}",
            "",
            "---",
            "",
        ]

        for msg in session.messages:
            role_display = {
                "user": "👤 **User**",
                "assistant": f"🤖 **{msg.model or 'Assistant'}**",
                "system": "⚙️ **System**",
                "tool": "🔧 **Tool**",
            }

            lines.append(role_display.get(msg.role.value, msg.role.value))
            lines.append("")
            lines.append(msg.content)
            lines.append("")

            if msg.tool_calls:
                lines.append("*Tool calls:*")
                for tc in msg.tool_calls:
                    lines.append(f"- `{tc.tool_name}`: {tc.parameters}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    async def import_session(self, data: str, format: str = "json") -> Session:
        """Import a session from JSON.

        Args:
            data: JSON string to import
            format: Import format (only 'json' supported)

        Returns:
            Imported Session
        """
        if format != "json":
            raise ValueError("Only JSON import is supported")

        parsed = json.loads(data)

        # Create new session with new ID
        session = await self.create_session(
            name=parsed.get("name"),
            project_path=parsed.get("project_path"),
            metadata=parsed.get("metadata"),
        )

        # Import messages
        for msg_data in parsed.get("messages", []):
            message_id = str(uuid.uuid4())

            await self.db.add_message(
                message_id=message_id,
                session_id=session.id,
                role=msg_data["role"],
                content=msg_data["content"],
                model=msg_data.get("model"),
                tokens_used=msg_data.get("tokens_used"),
                cost_estimate=msg_data.get("cost_estimate"),
            )

            # Import tool calls
            for tc_data in msg_data.get("tool_calls", []):
                await self.db.add_tool_call(
                    tool_call_id=str(uuid.uuid4()),
                    message_id=message_id,
                    tool_name=tc_data["tool_name"],
                    parameters=tc_data.get("parameters"),
                    result=tc_data.get("result"),
                    status=tc_data.get("status", "pending"),
                )

            # Handle pinned messages
            if msg_data.get("is_pinned"):
                await self.pin_message(message_id)

        return await self.load_session(session.id)

    # ========== Callbacks ==========

    def on_message_persisted(self, callback: Callable[[str], None]) -> None:
        """Register a callback for when messages are persisted.

        Args:
            callback: Function to call with message ID
        """
        self._on_message_persisted = callback


async def create_conversation_manager(
    db_path: str,
) -> ConversationManager:
    """Factory function to create a ConversationManager with initialized DB.

    Args:
        db_path: Path to SQLite database

    Returns:
        Initialized ConversationManager
    """
    db = DatabaseManager(db_path)
    await db.initialize()

    return ConversationManager(db=db)
