"""Tests for DatabaseManager batch operations and statistics."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from codecrew.conversation import DatabaseManager


@pytest_asyncio.fixture
async def db_manager(temp_dir: Path) -> DatabaseManager:
    """Create an initialized database manager."""
    db_path = temp_dir / "test_batch.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    return db


@pytest_asyncio.fixture
async def session_with_messages(db_manager: DatabaseManager) -> str:
    """Create a session with some messages and return session ID."""
    session_id = str(uuid.uuid4())
    await db_manager.create_session(session_id=session_id, name="Batch Test Session")

    # Add some messages
    for i in range(5):
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}",
            model="claude" if i % 2 == 1 else None,
            tokens_used=10 * (i + 1),
            cost_estimate=0.001 * (i + 1) if i % 2 == 1 else None,
        )

    return session_id


class TestBatchMessageOperations:
    """Tests for batch message operations."""

    @pytest.mark.asyncio
    async def test_batch_add_messages(self, db_manager: DatabaseManager) -> None:
        """Test adding multiple messages in a batch."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id, name="Batch Add Test")

        messages = [
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "user",
                "content": "First message",
            },
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "assistant",
                "content": "First response",
                "model": "claude",
                "tokens_used": 50,
                "cost_estimate": 0.001,
            },
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "user",
                "content": "Second message",
            },
        ]

        ids = await db_manager.batch_add_messages(messages)

        assert len(ids) == 3

        # Verify messages were added
        saved_messages = await db_manager.get_session_messages(session_id)
        assert len(saved_messages) == 3

    @pytest.mark.asyncio
    async def test_batch_add_messages_empty(self, db_manager: DatabaseManager) -> None:
        """Test batch add with empty list returns empty list."""
        ids = await db_manager.batch_add_messages([])
        assert ids == []

    @pytest.mark.asyncio
    async def test_batch_add_updates_session_timestamp(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that batch add updates the session's updated_at timestamp."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        original = await db_manager.get_session(session_id)
        original_updated = original["updated_at"]

        # Wait a tiny bit to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.1)

        messages = [
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "user",
                "content": "Test message",
            },
        ]
        await db_manager.batch_add_messages(messages)

        updated = await db_manager.get_session(session_id)
        assert updated["updated_at"] > original_updated


class TestBatchToolCallOperations:
    """Tests for batch tool call operations."""

    @pytest.mark.asyncio
    async def test_batch_add_tool_calls(self, db_manager: DatabaseManager) -> None:
        """Test adding multiple tool calls in a batch."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        message_id = str(uuid.uuid4())
        await db_manager.add_message(
            message_id=message_id,
            session_id=session_id,
            role="assistant",
            content="Using multiple tools",
        )

        tool_calls = [
            {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "tool_name": "read_file",
                "parameters": {"path": "/test/file1.txt"},
                "status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "tool_name": "write_file",
                "parameters": {"path": "/test/file2.txt", "content": "hello"},
                "status": "success",
                "result": {"success": True},
            },
            {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "tool_name": "execute_command",
                "parameters": {"command": "ls"},
                "status": "error",
                "result": {"error": "Permission denied"},
            },
        ]

        ids = await db_manager.batch_add_tool_calls(tool_calls)
        assert len(ids) == 3

        # Verify tool calls were added
        saved = await db_manager.get_message_tool_calls(message_id)
        assert len(saved) == 3

    @pytest.mark.asyncio
    async def test_batch_add_tool_calls_empty(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test batch add tool calls with empty list returns empty list."""
        ids = await db_manager.batch_add_tool_calls([])
        assert ids == []


class TestMessagesByModel:
    """Tests for filtering messages by model."""

    @pytest.mark.asyncio
    async def test_get_messages_by_model(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test getting messages from a specific model."""
        # Add messages from different models
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_with_messages,
            role="assistant",
            content="GPT response",
            model="gpt",
        )
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_with_messages,
            role="assistant",
            content="Another Claude response",
            model="claude",
        )

        claude_messages = await db_manager.get_messages_by_model(
            session_with_messages, "claude"
        )

        # Original fixture has 2 claude messages + 1 we just added = 3
        assert len(claude_messages) >= 3
        assert all(m["model"] == "claude" for m in claude_messages)

    @pytest.mark.asyncio
    async def test_get_messages_by_model_empty(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test getting messages from a model with no messages."""
        gemini_messages = await db_manager.get_messages_by_model(
            session_with_messages, "gemini"
        )
        assert len(gemini_messages) == 0


class TestSessionStats:
    """Tests for session statistics."""

    @pytest.mark.asyncio
    async def test_get_session_stats(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test getting session statistics."""
        stats = await db_manager.get_session_stats(session_with_messages)

        assert stats["total_messages"] == 5
        assert stats["total_tokens"] > 0
        assert "by_role" in stats
        assert "user" in stats["by_role"]
        assert "assistant" in stats["by_role"]
        assert "by_model" in stats
        assert "claude" in stats["by_model"]
        assert "pinned_count" in stats

    @pytest.mark.asyncio
    async def test_get_session_stats_with_pins(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test that stats include pinned message count."""
        messages = await db_manager.get_session_messages(session_with_messages)

        # Pin a couple messages
        await db_manager.pin_message(
            session_with_messages, messages[0]["id"], str(uuid.uuid4())
        )
        await db_manager.pin_message(
            session_with_messages, messages[1]["id"], str(uuid.uuid4())
        )

        stats = await db_manager.get_session_stats(session_with_messages)
        assert stats["pinned_count"] == 2


class TestMessageSearch:
    """Tests for message search functionality."""

    @pytest.mark.asyncio
    async def test_search_messages(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test searching messages within a session."""
        # Add some specific messages to search for
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_with_messages,
            role="user",
            content="Can you help me with authentication?",
        )
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_with_messages,
            role="assistant",
            content="Sure, let me explain authentication flow.",
            model="claude",
        )

        results = await db_manager.search_messages(
            session_with_messages, "authentication"
        )

        assert len(results) == 2
        assert all("authentication" in r["content"].lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_messages_no_results(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test search with no matching results."""
        results = await db_manager.search_messages(
            session_with_messages, "xyznonexistent123"
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_messages_with_limit(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test search with limit."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add many messages with searchable content
        for i in range(20):
            await db_manager.add_message(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role="user",
                content=f"Test searchable content number {i}",
            )

        results = await db_manager.search_messages(
            session_id, "searchable", limit=5
        )
        assert len(results) == 5


class TestDateRangeQuery:
    """Tests for date range queries."""

    @pytest.mark.asyncio
    async def test_get_messages_in_date_range(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test getting messages within a date range."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add a message
        await db_manager.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content="Message in range",
        )

        # Query with a range that includes now
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        results = await db_manager.get_messages_in_date_range(
            session_id, start, end
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_messages_in_date_range_empty(
        self, db_manager: DatabaseManager, session_with_messages: str
    ) -> None:
        """Test date range query with no results."""
        # Query a range in the past that shouldn't have any messages
        start = datetime.utcnow() - timedelta(days=365)
        end = datetime.utcnow() - timedelta(days=364)

        results = await db_manager.get_messages_in_date_range(
            session_with_messages, start, end
        )

        assert len(results) == 0


class TestSummaryOperations:
    """Tests for summary database operations."""

    @pytest.mark.asyncio
    async def test_add_summary(self, db_manager: DatabaseManager) -> None:
        """Test adding a summary."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        summary_id = str(uuid.uuid4())
        summary = await db_manager.add_summary(
            summary_id=summary_id,
            session_id=session_id,
            summary_type="incremental",
            content="This is a test summary of the conversation.",
            message_range_start="msg-1",
            message_range_end="msg-10",
            token_count=50,
        )

        assert summary["id"] == summary_id
        assert summary["summary_type"] == "incremental"
        assert summary["content"] == "This is a test summary of the conversation."
        assert summary["message_range_start"] == "msg-1"
        assert summary["message_range_end"] == "msg-10"
        assert summary["token_count"] == 50

    @pytest.mark.asyncio
    async def test_get_session_summaries(self, db_manager: DatabaseManager) -> None:
        """Test getting all summaries for a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add multiple summaries
        for i in range(3):
            await db_manager.add_summary(
                summary_id=str(uuid.uuid4()),
                session_id=session_id,
                summary_type="incremental" if i < 2 else "full",
                content=f"Summary {i}",
            )

        all_summaries = await db_manager.get_session_summaries(session_id)
        assert len(all_summaries) == 3

        incremental = await db_manager.get_session_summaries(
            session_id, summary_type="incremental"
        )
        assert len(incremental) == 2

    @pytest.mark.asyncio
    async def test_get_latest_summary(self, db_manager: DatabaseManager) -> None:
        """Test getting the latest summary."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        await db_manager.add_summary(
            summary_id=str(uuid.uuid4()),
            session_id=session_id,
            summary_type="incremental",
            content="First summary",
        )

        import asyncio
        await asyncio.sleep(0.1)  # Ensure different timestamp

        await db_manager.add_summary(
            summary_id=str(uuid.uuid4()),
            session_id=session_id,
            summary_type="incremental",
            content="Latest summary",
        )

        latest = await db_manager.get_latest_summary(session_id)
        assert latest is not None
        assert latest["content"] == "Latest summary"

    @pytest.mark.asyncio
    async def test_delete_session_summaries(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test deleting all summaries for a session."""
        session_id = str(uuid.uuid4())
        await db_manager.create_session(session_id=session_id)

        # Add summaries
        for i in range(3):
            await db_manager.add_summary(
                summary_id=str(uuid.uuid4()),
                session_id=session_id,
                summary_type="incremental",
                content=f"Summary {i}",
            )

        count = await db_manager.delete_session_summaries(session_id)
        assert count == 3

        remaining = await db_manager.get_session_summaries(session_id)
        assert len(remaining) == 0
