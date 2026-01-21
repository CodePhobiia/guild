"""Database schema migrations for CodeCrew."""

from typing import Callable, Coroutine, Any

import aiosqlite

# Type alias for migration functions
MigrationFunc = Callable[[aiosqlite.Connection], Coroutine[Any, Any, None]]

# Migration registry: version -> migration function
MIGRATIONS: dict[int, MigrationFunc] = {}


def migration(version: int) -> Callable[[MigrationFunc], MigrationFunc]:
    """Decorator to register a migration function."""

    def decorator(func: MigrationFunc) -> MigrationFunc:
        MIGRATIONS[version] = func
        return func

    return decorator


async def get_current_version(conn: aiosqlite.Connection) -> int:
    """Get the current schema version from the database."""
    # Check if schema_version table exists
    cursor = await conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_version'
        """
    )
    if await cursor.fetchone() is None:
        return 0

    cursor = await conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def set_version(conn: aiosqlite.Connection, version: int) -> None:
    """Set the schema version."""
    await conn.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
        (version,),
    )


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """Run all pending migrations."""
    current_version = await get_current_version(conn)

    # Get all versions that need to be applied
    pending_versions = sorted(v for v in MIGRATIONS.keys() if v > current_version)

    for version in pending_versions:
        migration_func = MIGRATIONS[version]
        await migration_func(conn)
        await set_version(conn, version)
        await conn.commit()


# ============================================================================
# Migration Definitions
# ============================================================================


@migration(1)
async def migration_001_initial_schema(conn: aiosqlite.Connection) -> None:
    """Create the initial database schema."""

    # Schema version tracking table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Sessions table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            project_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON
        )
        """
    )

    # Messages table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            content TEXT NOT NULL,
            tokens_used INTEGER,
            cost_estimate REAL,
            is_pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """
    )

    # Tool calls table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_calls (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            parameters JSON,
            result JSON,
            status TEXT,
            executed_at TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        )
        """
    )

    # Pinned context table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pinned_context (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        )
        """
    )

    # Create indexes for common queries
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON tool_calls(message_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pinned_context_session ON pinned_context(session_id)"
    )


@migration(2)
async def migration_002_add_summaries_table(conn: aiosqlite.Connection) -> None:
    """Add table for conversation summaries."""

    # Summaries table for context summarization
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            summary_type TEXT NOT NULL,
            content TEXT NOT NULL,
            message_range_start TEXT,
            message_range_end TEXT,
            token_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """
    )

    # Index for efficient summary lookup
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_summaries_session ON summaries(session_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_summaries_type ON summaries(session_id, summary_type)"
    )


# Future migrations can be added here:
# @migration(3)
# async def migration_003_add_some_feature(conn: aiosqlite.Connection) -> None:
#     """Add some new feature."""
#     await conn.execute("ALTER TABLE sessions ADD COLUMN new_field TEXT")
