"""Tests for ConversationManager."""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from codecrew.conversation import (
    ConversationManager,
    DatabaseManager,
    create_conversation_manager,
)
from codecrew.models.types import Message, MessageRole, ToolCall, Usage


@pytest_asyncio.fixture
async def conversation_manager(temp_dir: Path) -> ConversationManager:
    """Create a ConversationManager for tests."""
    db_path = temp_dir / "test_manager.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    return ConversationManager(db=db)


class TestSessionLifecycle:
    """Tests for session lifecycle management."""

    @pytest.mark.asyncio
    async def test_create_session(self, conversation_manager: ConversationManager) -> None:
        """Test creating a new session."""
        session = await conversation_manager.create_session(
            name="Test Session",
            project_path="/test/project",
        )

        assert session.id is not None
        assert session.name == "Test Session"
        assert session.project_path == "/test/project"
        assert conversation_manager.current_session_id == session.id

    @pytest.mark.asyncio
    async def test_load_session(self, conversation_manager: ConversationManager) -> None:
        """Test loading an existing session."""
        # Create a session
        session = await conversation_manager.create_session(name="Load Test")
        session_id = session.id

        # Create a new manager and load the session
        new_manager = ConversationManager(db=conversation_manager.db)
        loaded = await new_manager.load_session(session_id)

        assert loaded.id == session_id
        assert loaded.name == "Load Test"
        assert new_manager.current_session_id == session_id

    @pytest.mark.asyncio
    async def test_load_nonexistent_session_raises(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test that loading a non-existent session raises an error."""
        with pytest.raises(ValueError, match="Session not found"):
            await conversation_manager.load_session("nonexistent-id")

    @pytest.mark.asyncio
    async def test_switch_session(self, conversation_manager: ConversationManager) -> None:
        """Test switching between sessions."""
        session1 = await conversation_manager.create_session(name="Session 1")
        session2 = await conversation_manager.create_session(name="Session 2")

        # Currently on session2
        assert conversation_manager.current_session_id == session2.id

        # Switch to session1
        await conversation_manager.switch_session(session1.id)
        assert conversation_manager.current_session_id == session1.id

    @pytest.mark.asyncio
    async def test_list_sessions(self, conversation_manager: ConversationManager) -> None:
        """Test listing all sessions."""
        await conversation_manager.create_session(name="Session A")
        await conversation_manager.create_session(name="Session B")
        await conversation_manager.create_session(name="Session C")

        sessions = await conversation_manager.list_sessions()
        assert len(sessions) >= 3

    @pytest.mark.asyncio
    async def test_search_sessions(self, conversation_manager: ConversationManager) -> None:
        """Test searching sessions."""
        await conversation_manager.create_session(name="Authentication Feature")
        await conversation_manager.create_session(name="Bug Fix #123")

        results = await conversation_manager.search_sessions("Authentication")
        assert len(results) >= 1
        assert any(s.name == "Authentication Feature" for s in results)

    @pytest.mark.asyncio
    async def test_delete_session(self, conversation_manager: ConversationManager) -> None:
        """Test deleting a session."""
        session = await conversation_manager.create_session(name="To Delete")
        session_id = session.id

        result = await conversation_manager.delete_session(session_id)
        assert result is True
        assert conversation_manager.current_session_id is None

    @pytest.mark.asyncio
    async def test_archive_session(self, conversation_manager: ConversationManager) -> None:
        """Test archiving a session."""
        session = await conversation_manager.create_session(name="To Archive")

        result = await conversation_manager.archive_session()
        assert result is True
        assert conversation_manager.current_session_id is None


class TestMessagePersistence:
    """Tests for message persistence operations."""

    @pytest.mark.asyncio
    async def test_persist_user_message(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test persisting a user message."""
        await conversation_manager.create_session(name="Persist Test")

        message = Message.user("Hello, world!")
        message_id = await conversation_manager.persist_message(message)

        assert message_id is not None
        saved = await conversation_manager.get_message(message_id)
        assert saved is not None
        assert saved.content == "Hello, world!"
        assert saved.role.value == "user"

    @pytest.mark.asyncio
    async def test_persist_assistant_message_with_usage(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test persisting an assistant message with usage info."""
        await conversation_manager.create_session(name="Usage Test")

        message = Message.assistant("Hello! How can I help?", model="claude")
        usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30, cost_estimate=0.001)

        message_id = await conversation_manager.persist_message(message, usage=usage)

        saved = await conversation_manager.get_message(message_id)
        assert saved is not None
        assert saved.model == "claude"
        assert saved.tokens_used == 30
        assert saved.cost_estimate == 0.001

    @pytest.mark.asyncio
    async def test_persist_message_with_tool_calls(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test persisting a message with tool calls."""
        await conversation_manager.create_session(name="Tool Test")

        tool_call = ToolCall(id="tc-1", name="read_file", arguments={"path": "/test.txt"})
        message = Message.assistant("Let me read that file.", model="claude")
        message.tool_calls = [tool_call]

        message_id = await conversation_manager.persist_message(message)

        saved = await conversation_manager.get_message(message_id)
        assert saved is not None
        assert len(saved.tool_calls) == 1
        assert saved.tool_calls[0].tool_name == "read_file"

    @pytest.mark.asyncio
    async def test_persist_without_session_raises(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test that persisting without an active session raises an error."""
        message = Message.user("No session")

        with pytest.raises(ValueError, match="No active session"):
            await conversation_manager.persist_message(message)

    @pytest.mark.asyncio
    async def test_get_conversation_messages(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test retrieving conversation messages."""
        await conversation_manager.create_session(name="Conversation Test")

        await conversation_manager.persist_message(Message.user("Hello"))
        await conversation_manager.persist_message(
            Message.assistant("Hi there!", model="claude")
        )
        await conversation_manager.persist_message(Message.user("How are you?"))

        messages = await conversation_manager.get_conversation_messages()
        assert len(messages) == 3
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"
        assert messages[2].content == "How are you?"

    @pytest.mark.asyncio
    async def test_load_as_orchestrator_messages(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test loading messages as orchestrator Message objects."""
        await conversation_manager.create_session(name="Orchestrator Test")

        await conversation_manager.persist_message(Message.user("Test message"))
        await conversation_manager.persist_message(
            Message.assistant("Response", model="gpt")
        )

        orchestrator_messages = await conversation_manager.load_as_orchestrator_messages()

        assert len(orchestrator_messages) == 2
        assert orchestrator_messages[0].role == MessageRole.USER
        assert orchestrator_messages[1].role == MessageRole.ASSISTANT
        assert orchestrator_messages[1].model == "gpt"

    @pytest.mark.asyncio
    async def test_batch_persist_messages(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test persisting multiple messages."""
        await conversation_manager.create_session(name="Batch Test")

        messages = [
            Message.user("Message 1"),
            Message.assistant("Response 1", model="claude"),
            Message.user("Message 2"),
        ]

        message_ids = await conversation_manager.persist_messages(messages)
        assert len(message_ids) == 3

        saved = await conversation_manager.get_conversation_messages()
        assert len(saved) == 3


class TestPinOperations:
    """Tests for message pinning."""

    @pytest.mark.asyncio
    async def test_pin_message(self, conversation_manager: ConversationManager) -> None:
        """Test pinning a message."""
        await conversation_manager.create_session(name="Pin Test")

        message_id = await conversation_manager.persist_message(
            Message.user("Important context")
        )

        result = await conversation_manager.pin_message(message_id)
        assert result is True
        assert message_id in conversation_manager.pinned_ids

    @pytest.mark.asyncio
    async def test_unpin_message(self, conversation_manager: ConversationManager) -> None:
        """Test unpinning a message."""
        await conversation_manager.create_session(name="Unpin Test")

        message_id = await conversation_manager.persist_message(
            Message.user("Temporary pin")
        )

        await conversation_manager.pin_message(message_id)
        result = await conversation_manager.unpin_message(message_id)

        assert result is True
        assert message_id not in conversation_manager.pinned_ids

    @pytest.mark.asyncio
    async def test_get_pinned_messages(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test getting pinned messages."""
        await conversation_manager.create_session(name="Get Pins Test")

        msg1 = await conversation_manager.persist_message(Message.user("Pinned 1"))
        msg2 = await conversation_manager.persist_message(Message.user("Not pinned"))
        msg3 = await conversation_manager.persist_message(Message.user("Pinned 2"))

        await conversation_manager.pin_message(msg1)
        await conversation_manager.pin_message(msg3)

        pinned = await conversation_manager.get_pinned_messages()
        assert len(pinned) == 2
        pinned_ids = {m.id for m in pinned}
        assert msg1 in pinned_ids
        assert msg3 in pinned_ids
        assert msg2 not in pinned_ids

    @pytest.mark.asyncio
    async def test_sync_pins_from_db(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test syncing pins from database."""
        await conversation_manager.create_session(name="Sync Pins Test")

        msg_id = await conversation_manager.persist_message(Message.user("To sync"))
        await conversation_manager.pin_message(msg_id)

        # Clear in-memory pins
        conversation_manager._pinned_ids.clear()
        assert len(conversation_manager.pinned_ids) == 0

        # Sync from DB
        synced = await conversation_manager.sync_pins_from_db()
        assert msg_id in synced


class TestConversationStatistics:
    """Tests for conversation statistics."""

    @pytest.mark.asyncio
    async def test_get_conversation_stats(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test getting conversation statistics."""
        await conversation_manager.create_session(name="Stats Test")

        await conversation_manager.persist_message(
            Message.user("Hello"),
            usage=Usage(prompt_tokens=5, completion_tokens=0, total_tokens=5),
        )
        await conversation_manager.persist_message(
            Message.assistant("Hi!", model="claude"),
            usage=Usage(
                prompt_tokens=0,
                completion_tokens=10,
                total_tokens=10,
                cost_estimate=0.001,
            ),
        )
        await conversation_manager.persist_message(
            Message.assistant("How can I help?", model="gpt"),
            usage=Usage(
                prompt_tokens=0,
                completion_tokens=15,
                total_tokens=15,
                cost_estimate=0.002,
            ),
        )

        stats = await conversation_manager.get_conversation_stats()

        assert stats["total_messages"] == 3
        assert stats["total_tokens"] == 30
        assert stats["total_cost"] == 0.003
        assert stats["by_role"]["user"] == 1
        assert stats["by_role"]["assistant"] == 2
        assert "claude" in stats["by_model"]
        assert "gpt" in stats["by_model"]

    @pytest.mark.asyncio
    async def test_get_model_messages(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test getting messages from a specific model."""
        await conversation_manager.create_session(name="Model Filter Test")

        await conversation_manager.persist_message(Message.user("Hello"))
        await conversation_manager.persist_message(
            Message.assistant("Claude response", model="claude")
        )
        await conversation_manager.persist_message(
            Message.assistant("GPT response", model="gpt")
        )
        await conversation_manager.persist_message(
            Message.assistant("Another Claude", model="claude")
        )

        claude_messages = await conversation_manager.get_model_messages("claude")
        assert len(claude_messages) == 2
        assert all(m.model == "claude" for m in claude_messages)


class TestExportImport:
    """Tests for export and import functionality."""

    @pytest.mark.asyncio
    async def test_export_json(self, conversation_manager: ConversationManager) -> None:
        """Test exporting session as JSON."""
        await conversation_manager.create_session(name="Export JSON Test")

        await conversation_manager.persist_message(Message.user("Hello"))
        await conversation_manager.persist_message(
            Message.assistant("Hi!", model="claude")
        )

        json_export = await conversation_manager.export_session(format="json")

        assert "Export JSON Test" in json_export
        assert "Hello" in json_export
        assert "Hi!" in json_export
        assert "claude" in json_export

    @pytest.mark.asyncio
    async def test_export_markdown(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test exporting session as Markdown."""
        await conversation_manager.create_session(name="Export MD Test")

        await conversation_manager.persist_message(Message.user("Hello"))
        await conversation_manager.persist_message(
            Message.assistant("Hi!", model="claude")
        )

        md_export = await conversation_manager.export_session(format="markdown")

        assert "# Export MD Test" in md_export
        assert "User" in md_export
        assert "Hello" in md_export
        assert "claude" in md_export

    @pytest.mark.asyncio
    async def test_import_json(self, conversation_manager: ConversationManager) -> None:
        """Test importing a session from JSON."""
        # First export a session
        await conversation_manager.create_session(name="Original Session")
        await conversation_manager.persist_message(Message.user("Original message"))
        json_export = await conversation_manager.export_session(format="json")

        # Create a fresh manager and import
        new_manager = ConversationManager(db=conversation_manager.db)
        imported = await new_manager.import_session(json_export)

        assert imported.name == "Original Session"
        messages = await new_manager.get_conversation_messages()
        assert len(messages) == 1
        assert messages[0].content == "Original message"


class TestCallbacks:
    """Tests for callback functionality."""

    @pytest.mark.asyncio
    async def test_on_message_persisted_callback(
        self, conversation_manager: ConversationManager
    ) -> None:
        """Test that callback is called when message is persisted."""
        await conversation_manager.create_session(name="Callback Test")

        persisted_ids = []

        def callback(message_id: str) -> None:
            persisted_ids.append(message_id)

        conversation_manager.on_message_persisted(callback)

        msg_id = await conversation_manager.persist_message(Message.user("Test"))

        assert msg_id in persisted_ids


class TestFactoryFunction:
    """Tests for the factory function."""

    @pytest.mark.asyncio
    async def test_create_conversation_manager(self, temp_dir: Path) -> None:
        """Test the factory function creates a working manager."""
        db_path = str(temp_dir / "factory_test.db")
        manager = await create_conversation_manager(db_path)

        assert manager is not None

        session = await manager.create_session(name="Factory Test")
        assert session.id is not None
