"""Tests for the history manager module."""

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from codecrew.ui.history import HistoryEntry, HistoryManager, PersistentHistory


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_create_entry(self):
        """Test creating a new history entry."""
        entry = HistoryEntry.create(
            content="test message",
            entry_type="message",
            session_id="session-123",
        )

        assert entry.content == "test message"
        assert entry.entry_type == "message"
        assert entry.session_id == "session-123"
        assert entry.id is not None
        assert entry.timestamp is not None

    def test_create_entry_without_session(self):
        """Test creating entry without session ID."""
        entry = HistoryEntry.create(
            content="/help",
            entry_type="command",
        )

        assert entry.content == "/help"
        assert entry.entry_type == "command"
        assert entry.session_id is None

    def test_entry_timestamp_is_utc(self):
        """Test that timestamp is UTC."""
        entry = HistoryEntry.create(content="test", entry_type="message")
        assert entry.timestamp.tzinfo == timezone.utc


class TestHistoryManager:
    """Tests for HistoryManager class."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test_history.db")

    @pytest.fixture
    async def init_db(self, temp_db_path):
        """Initialize database with tables."""
        import aiosqlite

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    project_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS input_history (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    session_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON input_history(timestamp DESC)"
            )
            await conn.commit()

        return temp_db_path

    @pytest.fixture
    async def manager(self, init_db):
        """Create a HistoryManager instance."""
        return HistoryManager(db_path=init_db)

    @pytest.mark.asyncio
    async def test_add_entry(self, manager):
        """Test adding an entry to history."""
        entry = await manager.add_entry(
            content="hello world",
            entry_type="message",
        )

        assert entry is not None
        assert entry.content == "hello world"
        assert entry.entry_type == "message"

    @pytest.mark.asyncio
    async def test_add_empty_entry_returns_none(self, temp_db_path):
        """Test that empty entries are skipped."""
        manager = HistoryManager(db_path=temp_db_path)
        entry = await manager.add_entry(content="   ", entry_type="message")
        assert entry is None

    @pytest.mark.asyncio
    async def test_add_duplicate_returns_existing(self, manager):
        """Test that duplicates return the existing entry."""
        entry1 = await manager.add_entry(content="test", entry_type="message")
        entry2 = await manager.add_entry(content="test", entry_type="message")

        assert entry1.content == entry2.content

    @pytest.mark.asyncio
    async def test_get_recent(self, manager):
        """Test getting recent entries."""
        await manager.add_entry(content="first", entry_type="message")
        await manager.add_entry(content="second", entry_type="message")
        await manager.add_entry(content="third", entry_type="message")

        entries = await manager.get_recent(limit=10)

        # Most recent first
        assert len(entries) == 3
        assert entries[0].content == "third"
        assert entries[1].content == "second"
        assert entries[2].content == "first"

    @pytest.mark.asyncio
    async def test_get_recent_with_limit(self, manager):
        """Test limit on recent entries."""
        for i in range(10):
            await manager.add_entry(content=f"entry {i}", entry_type="message")

        entries = await manager.get_recent(limit=5)
        assert len(entries) == 5

    @pytest.mark.asyncio
    async def test_get_recent_by_type(self, manager):
        """Test filtering entries by type."""
        await manager.add_entry(content="message 1", entry_type="message")
        await manager.add_entry(content="/help", entry_type="command")
        await manager.add_entry(content="message 2", entry_type="message")
        await manager.add_entry(content="/quit", entry_type="command")

        messages = await manager.get_recent(entry_type="message")
        commands = await manager.get_recent(entry_type="command")

        assert len(messages) == 2
        assert len(commands) == 2
        assert all(e.entry_type == "message" for e in messages)
        assert all(e.entry_type == "command" for e in commands)

    @pytest.mark.asyncio
    async def test_search(self, manager):
        """Test searching history entries."""
        await manager.add_entry(content="hello world", entry_type="message")
        await manager.add_entry(content="goodbye world", entry_type="message")
        await manager.add_entry(content="hello there", entry_type="message")

        results = await manager.search("hello")

        assert len(results) == 2
        assert all("hello" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, manager):
        """Test that search is case-insensitive."""
        await manager.add_entry(content="HELLO World", entry_type="message")
        await manager.add_entry(content="hello there", entry_type="message")

        results = await manager.search("hello")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_commands(self, manager):
        """Test getting command history."""
        await manager.add_entry(content="message", entry_type="message")
        await manager.add_entry(content="/help", entry_type="command")
        await manager.add_entry(content="/quit", entry_type="command")

        commands = await manager.get_commands()

        assert len(commands) == 2
        assert all(e.entry_type == "command" for e in commands)

    @pytest.mark.asyncio
    async def test_get_messages(self, manager):
        """Test getting message history."""
        await manager.add_entry(content="hello", entry_type="message")
        await manager.add_entry(content="/help", entry_type="command")
        await manager.add_entry(content="world", entry_type="message")

        messages = await manager.get_messages()

        assert len(messages) == 2
        assert all(e.entry_type == "message" for e in messages)

    @pytest.mark.asyncio
    async def test_clear_all(self, manager):
        """Test clearing all history."""
        await manager.add_entry(content="test1", entry_type="message")
        await manager.add_entry(content="test2", entry_type="message")

        deleted = await manager.clear()

        assert deleted == 2
        entries = await manager.get_recent()
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_clear_by_type(self, manager):
        """Test clearing history by type."""
        await manager.add_entry(content="message", entry_type="message")
        await manager.add_entry(content="/help", entry_type="command")

        deleted = await manager.clear(entry_type="command")

        assert deleted == 1
        entries = await manager.get_recent()
        assert len(entries) == 1
        assert entries[0].entry_type == "message"

    @pytest.mark.asyncio
    async def test_get_count(self, manager):
        """Test getting entry count."""
        await manager.add_entry(content="test1", entry_type="message")
        await manager.add_entry(content="test2", entry_type="message")
        await manager.add_entry(content="/help", entry_type="command")

        total = await manager.get_count()
        messages = await manager.get_count(entry_type="message")
        commands = await manager.get_count(entry_type="command")

        assert total == 3
        assert messages == 2
        assert commands == 1

    @pytest.mark.asyncio
    async def test_session_association(self, manager):
        """Test associating entries with sessions."""
        manager.set_session("session-123")
        entry = await manager.add_entry(content="test", entry_type="message")

        assert entry.session_id == "session-123"

    @pytest.mark.asyncio
    async def test_get_strings_for_prompt_toolkit(self, manager):
        """Test getting history as strings in prompt_toolkit order."""
        await manager.add_entry(content="first", entry_type="message")
        await manager.add_entry(content="second", entry_type="message")
        await manager.add_entry(content="third", entry_type="message")

        strings = await manager.get_strings_for_prompt_toolkit()

        # Oldest first for prompt_toolkit
        assert strings == ["first", "second", "third"]


class TestPersistentHistory:
    """Tests for PersistentHistory wrapper class."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test_persistent.db")

    @pytest.fixture
    async def init_db(self, temp_db_path):
        """Initialize database with tables."""
        import aiosqlite

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS input_history (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    session_id TEXT
                )
            """)
            await conn.commit()

        return temp_db_path

    @pytest.fixture
    async def manager(self, init_db):
        """Create a HistoryManager instance."""
        return HistoryManager(db_path=init_db)

    @pytest.fixture
    def persistent_history(self, manager):
        """Create a PersistentHistory instance."""
        return PersistentHistory(history_manager=manager, entry_type="message")

    @pytest.mark.asyncio
    async def test_load(self, persistent_history, manager):
        """Test loading history."""
        await manager.add_entry(content="entry1", entry_type="message")
        await manager.add_entry(content="entry2", entry_type="message")

        await persistent_history.load()

        strings = persistent_history.load_history_strings()
        assert strings == ["entry1", "entry2"]

    @pytest.mark.asyncio
    async def test_append(self, persistent_history):
        """Test appending to history."""
        await persistent_history.append("new entry")

        strings = persistent_history.load_history_strings()
        assert "new entry" in strings

    @pytest.mark.asyncio
    async def test_load_history_strings_without_load(self, persistent_history):
        """Test that load_history_strings returns empty list before load."""
        strings = persistent_history.load_history_strings()
        assert strings == []

    @pytest.mark.asyncio
    async def test_append_updates_cache(self, persistent_history):
        """Test that append updates the cached strings."""
        await persistent_history.load()
        await persistent_history.append("cached entry")

        strings = persistent_history.load_history_strings()
        assert "cached entry" in strings
