"""Persistent input history manager."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiosqlite


@dataclass
class HistoryEntry:
    """A single entry in the input history."""

    id: str
    content: str
    timestamp: datetime
    entry_type: str  # "message" | "command"
    session_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        content: str,
        entry_type: str,
        session_id: Optional[str] = None,
    ) -> "HistoryEntry":
        """Create a new history entry."""
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            timestamp=datetime.now(timezone.utc),
            entry_type=entry_type,
            session_id=session_id,
        )


class HistoryManager:
    """Manages persistent input history with database storage.

    Stores both message input and command history separately,
    allowing for type-specific retrieval and search.
    """

    def __init__(
        self,
        db_path: str,
        max_entries: int = 10000,
    ):
        """Initialize the history manager.

        Args:
            db_path: Path to the SQLite database file
            max_entries: Maximum number of history entries to keep
        """
        self.db_path = db_path
        self.max_entries = max_entries
        self._current_session_id: Optional[str] = None

    def set_session(self, session_id: Optional[str]) -> None:
        """Set the current session ID for new entries."""
        self._current_session_id = session_id

    def _connect(self):
        """Get a database connection context manager."""
        return aiosqlite.connect(self.db_path)

    async def add_entry(
        self,
        content: str,
        entry_type: str = "message",
        session_id: Optional[str] = None,
    ) -> HistoryEntry:
        """Add a new entry to the history.

        Args:
            content: The input content to store
            entry_type: Type of entry ("message" or "command")
            session_id: Optional session ID (uses current if not provided)

        Returns:
            The created HistoryEntry
        """
        # Skip empty entries or duplicates of last entry
        content = content.strip()
        if not content:
            return None

        # Check for duplicate of last entry
        recent = await self.get_recent(limit=1, entry_type=entry_type)
        if recent and recent[0].content == content:
            return recent[0]

        entry = HistoryEntry.create(
            content=content,
            entry_type=entry_type,
            session_id=session_id or self._current_session_id,
        )

        async with self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO input_history (id, content, timestamp, entry_type, session_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.content,
                    entry.timestamp.isoformat(),
                    entry.entry_type,
                    entry.session_id,
                ),
            )
            await conn.commit()

            # Cleanup old entries if over limit
            await self._cleanup_old_entries(conn)

        return entry

    async def get_recent(
        self,
        limit: int = 100,
        entry_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[HistoryEntry]:
        """Get recent history entries.

        Args:
            limit: Maximum number of entries to return
            entry_type: Filter by entry type (None for all)
            session_id: Filter by session (None for all)

        Returns:
            List of history entries, most recent first
        """
        async with self._connect() as conn:
            query = "SELECT id, content, timestamp, entry_type, session_id FROM input_history"
            conditions = []
            params = []

            if entry_type:
                conditions.append("entry_type = ?")
                params.append(entry_type)

            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

            return [
                HistoryEntry(
                    id=row[0],
                    content=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    entry_type=row[3],
                    session_id=row[4],
                )
                for row in rows
            ]

    async def search(
        self,
        query: str,
        limit: int = 50,
        entry_type: Optional[str] = None,
    ) -> list[HistoryEntry]:
        """Search history entries by content.

        Args:
            query: Search query (case-insensitive substring match)
            limit: Maximum number of results
            entry_type: Filter by entry type (None for all)

        Returns:
            List of matching entries, most recent first
        """
        async with self._connect() as conn:
            sql = """
                SELECT id, content, timestamp, entry_type, session_id
                FROM input_history
                WHERE content LIKE ?
            """
            params = [f"%{query}%"]

            if entry_type:
                sql += " AND entry_type = ?"
                params.append(entry_type)

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()

            return [
                HistoryEntry(
                    id=row[0],
                    content=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    entry_type=row[3],
                    session_id=row[4],
                )
                for row in rows
            ]

    async def get_commands(self, limit: int = 100) -> list[HistoryEntry]:
        """Get command history entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of command entries
        """
        return await self.get_recent(limit=limit, entry_type="command")

    async def get_messages(self, limit: int = 100) -> list[HistoryEntry]:
        """Get message history entries.

        Args:
            limit: Maximum number of entries

        Returns:
            List of message entries
        """
        return await self.get_recent(limit=limit, entry_type="message")

    async def clear(
        self,
        older_than: Optional[datetime] = None,
        entry_type: Optional[str] = None,
    ) -> int:
        """Clear history entries.

        Args:
            older_than: Only delete entries older than this time
            entry_type: Only delete entries of this type

        Returns:
            Number of entries deleted
        """
        async with self._connect() as conn:
            query = "DELETE FROM input_history"
            conditions = []
            params = []

            if older_than:
                conditions.append("timestamp < ?")
                params.append(older_than.isoformat())

            if entry_type:
                conditions.append("entry_type = ?")
                params.append(entry_type)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.rowcount

    async def get_count(self, entry_type: Optional[str] = None) -> int:
        """Get the total number of history entries.

        Args:
            entry_type: Filter by entry type (None for all)

        Returns:
            Number of entries
        """
        async with self._connect() as conn:
            if entry_type:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM input_history WHERE entry_type = ?",
                    (entry_type,),
                )
            else:
                cursor = await conn.execute("SELECT COUNT(*) FROM input_history")

            row = await cursor.fetchone()
            return row[0] if row else 0

    async def _cleanup_old_entries(self, conn: aiosqlite.Connection) -> None:
        """Remove old entries when over the limit."""
        count = await conn.execute("SELECT COUNT(*) FROM input_history")
        row = await count.fetchone()
        total = row[0] if row else 0

        if total > self.max_entries:
            # Delete oldest entries to get back under limit
            excess = total - self.max_entries
            await conn.execute(
                """
                DELETE FROM input_history
                WHERE id IN (
                    SELECT id FROM input_history
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
                """,
                (excess,),
            )
            await conn.commit()

    async def get_strings_for_prompt_toolkit(
        self,
        entry_type: Optional[str] = None,
        limit: int = 1000,
    ) -> list[str]:
        """Get history as a list of strings for prompt_toolkit.

        Args:
            entry_type: Filter by type (None for all)
            limit: Maximum entries

        Returns:
            List of content strings, oldest first (for prompt_toolkit)
        """
        entries = await self.get_recent(limit=limit, entry_type=entry_type)
        # Reverse so oldest is first (prompt_toolkit expects this order)
        return [e.content for e in reversed(entries)]


class PersistentHistory:
    """A prompt_toolkit compatible history backed by HistoryManager.

    This class wraps HistoryManager to provide the interface
    expected by prompt_toolkit's PromptSession.
    """

    def __init__(
        self,
        history_manager: HistoryManager,
        entry_type: str = "message",
    ):
        """Initialize the persistent history.

        Args:
            history_manager: The underlying HistoryManager
            entry_type: Type of entries to store/retrieve
        """
        self.history_manager = history_manager
        self.entry_type = entry_type
        self._loaded_strings: list[str] = []

    def load_history_strings(self) -> list[str]:
        """Load history strings synchronously.

        Note: This is called by prompt_toolkit synchronously,
        so we use cached data loaded during initialization.
        """
        return self._loaded_strings

    def store_string(self, string: str) -> None:
        """Store a string in history.

        Note: prompt_toolkit calls this synchronously, but we need async.
        The actual storage happens via add_entry_sync or in the main loop.
        """
        # This will be handled asynchronously by the caller
        pass

    async def load(self, limit: int = 1000) -> None:
        """Load history from database asynchronously.

        Call this before using the history with prompt_toolkit.
        """
        self._loaded_strings = await self.history_manager.get_strings_for_prompt_toolkit(
            entry_type=self.entry_type,
            limit=limit,
        )

    async def append(self, content: str) -> None:
        """Append a new entry to history asynchronously."""
        await self.history_manager.add_entry(
            content=content,
            entry_type=self.entry_type,
        )
        # Also update the cached list
        if content not in self._loaded_strings:
            self._loaded_strings.append(content)
