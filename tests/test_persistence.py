"""Tests for database persistence."""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from codecrew.conversation import DatabaseManager
from codecrew.conversation.migrations import get_current_version


class TestDatabaseManager:
    """Tests for DatabaseManager."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, temp_dir: Path) -> None:
        """Test that initialize creates the database file."""
        db_path = temp_dir / "new_test.db"
        assert not db_path.exists()

        db = DatabaseManager(db_path)
        await db.initialize()

        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, db_manager: DatabaseManager) -> None:
        """Test that initialize creates all required tables."""
        tables = await db_manager.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {t["name"] for t in tables}

        assert "sessions" in table_names
        assert "messages" in table_names
        assert "tool_calls" in table_names
        assert "pinned_context" in table_names
        assert "schema_version" in table_names

    @pytest.mark.asyncio
    async def test_migrations_are_idempotent(self, temp_dir: Path) -> None:
        """Test that running migrations multiple times is safe."""
        db_path = temp_dir / "idempotent_test.db"
        db = DatabaseManager(db_path)

        # Run initialize twice
        await db.initialize()
        await db.initialize()

        # Should still work
        version = await db.get_version()
        assert version >= 1


class TestSessionOperations:
    """Tests for session CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, db_manager: DatabaseManager) -> None:
        """Test creating a session."""
        session_id = str(uuid.uuid4())
        session = await db_manager.create_session(
            session_id=session_id,
            name="Test Session",
            project_path="/test/path",
            metadata={"key": "value"},
        )

        assert session["id"] == session_id
        assert session["name"] == "Test Session"
        assert session["project_path"] == "/test/path"

    @pytest.mark.asyncio
    async def test_get_session(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id, name="Get Test")

        session = await db_manager.get_session(session_id)
        assert session is not None
        assert session["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, db_manager: DatabaseManager) -> None:
        """Test retrieving a non-existent session returns None."""
        session = await db_manager.get_session("nonexistent-id")
        assert session is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, db_manager: DatabaseManager) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(3):
            await db_manager.create_session(
                session_id=str(uuid.uuid4()),
                name=f"Session {i}",
            )

        sessions = await db_manager.list_sessions()
        assert len(sessions) >= 3

    @pytest.mark.asyncio
    async def test_list_sessions_limit(self, db_manager: DatabaseManager) -> None:
        """Test listing sessions with limit."""
        # Create multiple sessions
        for i in range(5):
            await db_manager.create_session(
                session_id=str(uuid.uuid4()),
                name=f"Limited Session {i}",
            )

        sessions = await db_manager.list_sessions(limit=2)
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_update_session(self, db_manager: DatabaseManager) -> None:
        """Test updating a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id, name="Original")

        updated = await db_manager.update_session(
            session_id=session_id,
            name="Updated Name",
            metadata={"updated": True},
        )

        assert updated["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_session(self, db_manager: DatabaseManager) -> None:
        """Test deleting a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id, name="To Delete")

        result = await db_manager.delete_session(session_id)
        assert result is True

        session = await db_manager.get_session(session_id)
        assert session is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, db_manager: DatabaseManager) -> None:
        """Test deleting a non-existent session returns False."""
        result = await db_manager.delete_session("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_search_sessions(self, db_manager: DatabaseManager) -> None:
        """Test searching sessions."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(
            session_id=session_id,
            name="Authentication Bug Fix",
        )

        results = await db_manager.search_sessions("Authentication")
        assert len(results) >= 1
        assert any(s["id"] == session_id for s in results)


class TestMessageOperations:
    """Tests for message CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_message(self, db_manager: DatabaseManager) -> None:
        """Test adding a message."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        message = await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            content="Hello, world!",
        )

        assert message["id"] == message_id
        assert message["content"] == "Hello, world!"
        assert message["role"] == "user"

    @pytest.mark.asyncio
    async def test_add_assistant_message(self, db_manager: DatabaseManager) -> None:
        """Test adding an assistant message with model info."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        message = await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            content="Hello! How can I help?",
            model="claude",
            tokens_used=50,
            cost_estimate=0.001,
        )

        assert message["model"] == "claude"
        assert message["tokens_used"] == 50
        assert message["cost_estimate"] == 0.001

    @pytest.mark.asyncio
    async def test_get_session_messages(self, db_manager: DatabaseManager) -> None:
        """Test retrieving messages for a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add multiple messages
        for i in range(3):
            await db_manager.add_message(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        messages = await db_manager.get_session_messages(session_id)
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_messages_ordered_chronologically(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that messages are returned in chronological order."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add messages
        ids = []
        for i in range(3):
            msg_id = str(uuid.uuid4())
            ids.append(msg_id)
            await db_manager.add_message(
                message_id=msg_id,
                session_id=session_id,
                role="user",
                content=f"Message {i}",
            )

        messages = await db_manager.get_session_messages(session_id)
        # First message should be first in list
        assert messages[0]["id"] == ids[0]

    @pytest.mark.asyncio
    async def test_pin_message(self, db_manager: DatabaseManager) -> None:
        """Test pinning a message."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            content="Important context",
        )

        pin_id = str(uuid.uuid4())
        await db_manager.pin_message(session_id, message_id, pin_id)

        message = await db_manager.get_message(message_id)
        assert bool(message["is_pinned"]) is True

        pinned = await db_manager.get_pinned_messages(session_id)
        assert len(pinned) == 1
        assert pinned[0]["id"] == message_id

    @pytest.mark.asyncio
    async def test_unpin_message(self, db_manager: DatabaseManager) -> None:
        """Test unpinning a message."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            content="Temporary pin",
        )

        pin_id = str(uuid.uuid4())
        await db_manager.pin_message(session_id, message_id, pin_id)
        await db_manager.unpin_message(message_id)

        message = await db_manager.get_message(message_id)
        assert bool(message["is_pinned"]) is False

        pinned = await db_manager.get_pinned_messages(session_id)
        assert len(pinned) == 0


class TestToolCallOperations:
    """Tests for tool call operations."""

    @pytest.mark.asyncio
    async def test_add_tool_call(self, db_manager: DatabaseManager) -> None:
        """Test adding a tool call."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            content="Let me read that file.",
        )

        tool_call_id = str(uuid.uuid4())
        tool_call = await db_manager.add_tool_call(
            tool_call_id=tool_call_id,
            message_id=message_id,
            tool_name="read_file",
            parameters={"path": "/test/file.txt"},
        )

        assert tool_call["id"] == tool_call_id
        assert tool_call["tool_name"] == "read_file"
        assert tool_call["status"] == "pending"

    @pytest.mark.asyncio
    async def test_update_tool_call(self, db_manager: DatabaseManager) -> None:
        """Test updating a tool call with results."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            content="Running command.",
        )

        tool_call_id = str(uuid.uuid4())
        await db_manager.add_tool_call(
            tool_call_id=tool_call_id,
            message_id=message_id,
            tool_name="execute_command",
            parameters={"command": "ls"},
        )

        updated = await db_manager.update_tool_call(
            tool_call_id=tool_call_id,
            result={"output": "file1.txt\nfile2.txt"},
            status="success",
        )

        assert updated["status"] == "success"
        assert updated["executed_at"] is not None

    @pytest.mark.asyncio
    async def test_get_message_tool_calls(self, db_manager: DatabaseManager) -> None:
        """Test getting tool calls for a message."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            content="Multiple tool calls.",
        )

        # Add multiple tool calls
        for i in range(3):
            await db_manager.add_tool_call(
                tool_call_id=str(uuid.uuid4()),
                message_id=message_id,
                tool_name=f"tool_{i}",
            )

        tool_calls = await db_manager.get_message_tool_calls(message_id)
        assert len(tool_calls) == 3


class TestCascadeDelete:
    """Tests for cascade delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_session_cascades_to_messages(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that deleting a session also deletes its messages."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            content="Test message",
        )

        await db_manager.delete_session(session_id)

        message = await db_manager.get_message(message_id)
        assert message is None
