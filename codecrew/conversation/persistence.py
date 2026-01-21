"""Database manager for conversation persistence using SQLite."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import aiosqlite

from .migrations import MIGRATIONS, get_current_version, run_migrations


class DatabaseManager:
    """Async SQLite database manager for conversation persistence."""

    def __init__(self, db_path: str | Path):
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database, creating it and running migrations if needed."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect and run migrations
        async with self.connect() as conn:
            await run_migrations(conn)

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection as an async context manager."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def execute(
        self, query: str, params: tuple = (), *, commit: bool = True
    ) -> aiosqlite.Cursor:
        """Execute a query and optionally commit.

        Args:
            query: SQL query to execute
            params: Query parameters
            commit: Whether to commit after execution

        Returns:
            Cursor with results
        """
        async with self.connect() as conn:
            cursor = await conn.execute(query, params)
            if commit:
                await conn.commit()
            return cursor

    async def execute_many(
        self, query: str, params_list: list[tuple], *, commit: bool = True
    ) -> None:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            commit: Whether to commit after execution
        """
        async with self.connect() as conn:
            await conn.executemany(query, params_list)
            if commit:
                await conn.commit()

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as a dictionary.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Row as dictionary or None if not found
        """
        async with self.connect() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as a list of dictionaries.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of rows as dictionaries
        """
        async with self.connect() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_version(self) -> int:
        """Get the current schema version."""
        async with self.connect() as conn:
            return await get_current_version(conn)

    # Session operations

    async def create_session(
        self,
        session_id: str,
        name: Optional[str] = None,
        project_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create a new session.

        Args:
            session_id: Unique session identifier
            name: Optional session name
            project_path: Optional project path
            metadata: Optional metadata dictionary

        Returns:
            Created session as dictionary
        """
        now = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        async with self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, name, project_path, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, name, project_path, now, now, metadata_json),
            )
            await conn.commit()

        return await self.get_session(session_id)

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get a session by ID."""
        return await self.fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))

    async def list_sessions(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List all sessions, ordered by most recent."""
        return await self.fetch_all(
            """
            SELECT * FROM sessions
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

    async def update_session(
        self,
        session_id: str,
        name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """Update a session."""
        now = datetime.now(UTC).isoformat()

        updates = ["updated_at = ?"]
        params: list[Any] = [now]

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        params.append(session_id)

        async with self.connect() as conn:
            await conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            await conn.commit()

        return await self.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        async with self.connect() as conn:
            cursor = await conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await conn.commit()
            return cursor.rowcount > 0

    async def search_sessions(self, query: str) -> list[dict]:
        """Search sessions by name or message content."""
        search_pattern = f"%{query}%"
        return await self.fetch_all(
            """
            SELECT DISTINCT s.* FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            WHERE s.name LIKE ? OR m.content LIKE ?
            ORDER BY s.updated_at DESC
            """,
            (search_pattern, search_pattern),
        )

    # Message operations

    async def add_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
    ) -> dict:
        """Add a message to a session."""
        now = datetime.now(UTC).isoformat()

        async with self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO messages
                (id, session_id, role, model, content, tokens_used, cost_estimate, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, model, content, tokens_used, cost_estimate, now),
            )
            # Update session's updated_at
            await conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await conn.commit()

        return await self.get_message(message_id)

    async def get_message(self, message_id: str) -> Optional[dict]:
        """Get a message by ID."""
        return await self.fetch_one("SELECT * FROM messages WHERE id = ?", (message_id,))

    async def get_session_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> list[dict]:
        """Get all messages for a session, in chronological order."""
        query = """
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """
        params: tuple = (session_id,)

        if limit is not None:
            query += " LIMIT ?"
            params = (session_id, limit)

        return await self.fetch_all(query, params)

    async def pin_message(self, session_id: str, message_id: str, pin_id: str) -> None:
        """Pin a message to a session's context."""
        now = datetime.now(UTC).isoformat()
        async with self.connect() as conn:
            # Update message is_pinned flag
            await conn.execute(
                "UPDATE messages SET is_pinned = TRUE WHERE id = ?", (message_id,)
            )
            # Add to pinned_context table
            await conn.execute(
                """
                INSERT OR IGNORE INTO pinned_context (id, session_id, message_id, pinned_at)
                VALUES (?, ?, ?, ?)
                """,
                (pin_id, session_id, message_id, now),
            )
            await conn.commit()

    async def unpin_message(self, message_id: str) -> None:
        """Unpin a message."""
        async with self.connect() as conn:
            await conn.execute(
                "UPDATE messages SET is_pinned = FALSE WHERE id = ?", (message_id,)
            )
            await conn.execute(
                "DELETE FROM pinned_context WHERE message_id = ?", (message_id,)
            )
            await conn.commit()

    async def get_pinned_messages(self, session_id: str) -> list[dict]:
        """Get all pinned messages for a session."""
        return await self.fetch_all(
            """
            SELECT m.* FROM messages m
            JOIN pinned_context pc ON m.id = pc.message_id
            WHERE pc.session_id = ?
            ORDER BY pc.pinned_at ASC
            """,
            (session_id,),
        )

    # Tool call operations

    async def add_tool_call(
        self,
        tool_call_id: str,
        message_id: str,
        tool_name: str,
        parameters: Optional[dict] = None,
        result: Optional[dict] = None,
        status: str = "pending",
    ) -> dict:
        """Add a tool call record."""
        now = datetime.now(UTC).isoformat() if status != "pending" else None

        async with self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO tool_calls
                (id, message_id, tool_name, parameters, result, status, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_call_id,
                    message_id,
                    tool_name,
                    json.dumps(parameters) if parameters else None,
                    json.dumps(result) if result else None,
                    status,
                    now,
                ),
            )
            await conn.commit()

        return await self.get_tool_call(tool_call_id)

    async def get_tool_call(self, tool_call_id: str) -> Optional[dict]:
        """Get a tool call by ID."""
        return await self.fetch_one("SELECT * FROM tool_calls WHERE id = ?", (tool_call_id,))

    async def update_tool_call(
        self,
        tool_call_id: str,
        result: Optional[dict] = None,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        """Update a tool call with result and status."""
        now = datetime.now(UTC).isoformat()

        updates = ["executed_at = ?"]
        params: list[Any] = [now]

        if result is not None:
            updates.append("result = ?")
            params.append(json.dumps(result))

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        params.append(tool_call_id)

        async with self.connect() as conn:
            await conn.execute(
                f"UPDATE tool_calls SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            await conn.commit()

        return await self.get_tool_call(tool_call_id)

    async def get_message_tool_calls(self, message_id: str) -> list[dict]:
        """Get all tool calls for a message."""
        return await self.fetch_all(
            "SELECT * FROM tool_calls WHERE message_id = ? ORDER BY executed_at ASC",
            (message_id,),
        )

    # Batch operations

    async def batch_add_messages(
        self,
        messages: list[dict],
    ) -> list[str]:
        """Add multiple messages in a single transaction.

        Args:
            messages: List of message dictionaries with keys:
                - id: Message ID
                - session_id: Session ID
                - role: Message role
                - content: Message content
                - model: Optional model name
                - tokens_used: Optional token count
                - cost_estimate: Optional cost

        Returns:
            List of created message IDs
        """
        if not messages:
            return []

        now = datetime.now(UTC).isoformat()
        session_ids = set()

        async with self.connect() as conn:
            for msg in messages:
                await conn.execute(
                    """
                    INSERT INTO messages
                    (id, session_id, role, model, content, tokens_used, cost_estimate, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg["id"],
                        msg["session_id"],
                        msg["role"],
                        msg.get("model"),
                        msg["content"],
                        msg.get("tokens_used"),
                        msg.get("cost_estimate"),
                        now,
                    ),
                )
                session_ids.add(msg["session_id"])

            # Update session timestamps
            for session_id in session_ids:
                await conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )

            await conn.commit()

        return [msg["id"] for msg in messages]

    async def batch_add_tool_calls(
        self,
        tool_calls: list[dict],
    ) -> list[str]:
        """Add multiple tool calls in a single transaction.

        Args:
            tool_calls: List of tool call dictionaries with keys:
                - id: Tool call ID
                - message_id: Message ID
                - tool_name: Tool name
                - parameters: Optional parameters dict
                - result: Optional result dict
                - status: Status string

        Returns:
            List of created tool call IDs
        """
        if not tool_calls:
            return []

        async with self.connect() as conn:
            for tc in tool_calls:
                executed_at = datetime.now(UTC).isoformat() if tc.get("status") != "pending" else None
                await conn.execute(
                    """
                    INSERT INTO tool_calls
                    (id, message_id, tool_name, parameters, result, status, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tc["id"],
                        tc["message_id"],
                        tc["tool_name"],
                        json.dumps(tc.get("parameters")) if tc.get("parameters") else None,
                        json.dumps(tc.get("result")) if tc.get("result") else None,
                        tc.get("status", "pending"),
                        executed_at,
                    ),
                )

            await conn.commit()

        return [tc["id"] for tc in tool_calls]

    async def get_messages_by_model(
        self,
        session_id: str,
        model_name: str,
    ) -> list[dict]:
        """Get all messages from a specific model in a session.

        Args:
            session_id: Session ID
            model_name: Model name to filter by

        Returns:
            List of messages from that model
        """
        return await self.fetch_all(
            """
            SELECT * FROM messages
            WHERE session_id = ? AND model = ?
            ORDER BY created_at ASC
            """,
            (session_id, model_name),
        )

    async def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session statistics
        """
        async with self.connect() as conn:
            # Total messages and tokens
            cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) as total_messages,
                    COALESCE(SUM(tokens_used), 0) as total_tokens,
                    COALESCE(SUM(cost_estimate), 0) as total_cost
                FROM messages
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            stats = dict(row) if row else {"total_messages": 0, "total_tokens": 0, "total_cost": 0}

            # Messages by role
            cursor = await conn.execute(
                """
                SELECT role, COUNT(*) as count
                FROM messages
                WHERE session_id = ?
                GROUP BY role
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
            stats["by_role"] = {row["role"]: row["count"] for row in rows}

            # Messages by model
            cursor = await conn.execute(
                """
                SELECT
                    model,
                    COUNT(*) as message_count,
                    COALESCE(SUM(tokens_used), 0) as tokens,
                    COALESCE(SUM(cost_estimate), 0) as cost
                FROM messages
                WHERE session_id = ? AND model IS NOT NULL
                GROUP BY model
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
            stats["by_model"] = {
                row["model"]: {
                    "messages": row["message_count"],
                    "tokens": row["tokens"],
                    "cost": row["cost"],
                }
                for row in rows
            }

            # Pinned count
            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM pinned_context WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            stats["pinned_count"] = row["count"] if row else 0

            return stats

    async def search_messages(
        self,
        session_id: str,
        query: str,
        limit: int = 50,
    ) -> list[dict]:
        """Search messages within a session.

        Args:
            session_id: Session ID
            query: Search query
            limit: Maximum results

        Returns:
            Matching messages
        """
        search_pattern = f"%{query}%"
        return await self.fetch_all(
            """
            SELECT * FROM messages
            WHERE session_id = ? AND content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, search_pattern, limit),
        )

    async def get_messages_in_date_range(
        self,
        session_id: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """Get messages within a date range.

        Args:
            session_id: Session ID
            start: Start datetime
            end: End datetime

        Returns:
            Messages in the range
        """
        return await self.fetch_all(
            """
            SELECT * FROM messages
            WHERE session_id = ?
              AND created_at >= ?
              AND created_at <= ?
            ORDER BY created_at ASC
            """,
            (session_id, start.isoformat(), end.isoformat()),
        )

    # Summary operations

    async def add_summary(
        self,
        summary_id: str,
        session_id: str,
        summary_type: str,
        content: str,
        message_range_start: Optional[str] = None,
        message_range_end: Optional[str] = None,
        token_count: Optional[int] = None,
    ) -> dict:
        """Add a conversation summary.

        Args:
            summary_id: Unique summary ID
            session_id: Session this summary belongs to
            summary_type: Type of summary ('early', 'mid', 'full', 'incremental')
            content: Summary content
            message_range_start: First message ID in summarized range
            message_range_end: Last message ID in summarized range
            token_count: Token count of the summary

        Returns:
            Created summary as dictionary
        """
        now = datetime.now(UTC).isoformat()

        async with self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO summaries
                (id, session_id, summary_type, content, message_range_start,
                 message_range_end, token_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    session_id,
                    summary_type,
                    content,
                    message_range_start,
                    message_range_end,
                    token_count,
                    now,
                ),
            )
            await conn.commit()

        return await self.get_summary(summary_id)

    async def get_summary(self, summary_id: str) -> Optional[dict]:
        """Get a summary by ID."""
        return await self.fetch_one("SELECT * FROM summaries WHERE id = ?", (summary_id,))

    async def get_session_summaries(
        self,
        session_id: str,
        summary_type: Optional[str] = None,
    ) -> list[dict]:
        """Get all summaries for a session.

        Args:
            session_id: Session ID
            summary_type: Optional type filter

        Returns:
            List of summaries
        """
        if summary_type:
            return await self.fetch_all(
                """
                SELECT * FROM summaries
                WHERE session_id = ? AND summary_type = ?
                ORDER BY created_at ASC
                """,
                (session_id, summary_type),
            )
        else:
            return await self.fetch_all(
                """
                SELECT * FROM summaries
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            )

    async def get_latest_summary(
        self,
        session_id: str,
        summary_type: Optional[str] = None,
    ) -> Optional[dict]:
        """Get the most recent summary for a session.

        Args:
            session_id: Session ID
            summary_type: Optional type filter

        Returns:
            Latest summary or None
        """
        if summary_type:
            return await self.fetch_one(
                """
                SELECT * FROM summaries
                WHERE session_id = ? AND summary_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id, summary_type),
            )
        else:
            return await self.fetch_one(
                """
                SELECT * FROM summaries
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            )

    async def delete_session_summaries(self, session_id: str) -> int:
        """Delete all summaries for a session.

        Args:
            session_id: Session ID

        Returns:
            Number of deleted summaries
        """
        async with self.connect() as conn:
            cursor = await conn.execute(
                "DELETE FROM summaries WHERE session_id = ?",
                (session_id,),
            )
            await conn.commit()
            return cursor.rowcount
