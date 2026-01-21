"""Tool context tracking for CodeCrew.

Tracks file modifications and reads across tool executions to:
- Detect when files have been modified since last read (staleness)
- Provide a summary of modifications made during a session
- Help models understand the current state of files they've touched

This enables smarter tool usage by allowing models to know whether
they need to re-read files after modifications.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class FileModification:
    """Record of a file modification operation.

    Attributes:
        path: Absolute path to the modified file.
        operation: Type of operation performed.
        timestamp: When the modification occurred.
        content_hash: Hash of file content after modification (if available).
        details: Optional details about the modification.
    """

    path: str
    operation: str  # "create", "write", "edit", "delete"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: Optional[str] = None
    details: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable representation."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.operation}: {self.path}"


@dataclass
class FileReadRecord:
    """Record of a file read operation.

    Attributes:
        path: Absolute path to the file.
        content_hash: Hash of file content when read.
        timestamp: When the file was read.
    """

    path: str
    content_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ToolContext:
    """Tracks context across tool executions in a session.

    Maintains records of file modifications and reads to enable:
    - Staleness detection (file changed since last read)
    - Modification summaries for context
    - Understanding of what files have been touched

    Example:
        >>> context = ToolContext()
        >>> context.record_read("/path/to/file.py", "abc123")
        >>> context.record_modification("/path/to/file.py", "edit")
        >>> context.is_file_stale("/path/to/file.py", "abc123")
        True  # File was modified after read
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    modifications: list[FileModification] = field(default_factory=list)
    read_files: dict[str, FileReadRecord] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_modification(
        self,
        path: str,
        operation: str,
        content_hash: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        """Record a file modification.

        Args:
            path: Absolute path to the modified file.
            operation: Type of operation ("create", "write", "edit", "delete").
            content_hash: Hash of content after modification.
            details: Optional details about the modification.
        """
        modification = FileModification(
            path=path,
            operation=operation,
            content_hash=content_hash,
            details=details,
        )
        self.modifications.append(modification)
        logger.debug(f"Recorded modification: {modification}")

    def record_read(self, path: str, content_hash: str) -> None:
        """Record a file read.

        Args:
            path: Absolute path to the file.
            content_hash: Hash of the file content.
        """
        self.read_files[path] = FileReadRecord(
            path=path,
            content_hash=content_hash,
        )
        logger.debug(f"Recorded read: {path} (hash: {content_hash[:8]}...)")

    def is_file_stale(self, path: str, current_hash: str) -> bool:
        """Check if a file has been modified since it was last read.

        Args:
            path: Path to check.
            current_hash: Current content hash of the file.

        Returns:
            True if the file was read before and has changed since.
            False if file wasn't read or hasn't changed.
        """
        record = self.read_files.get(path)
        if record is None:
            return False  # Never read, so not "stale"

        return record.content_hash != current_hash

    def was_file_modified(self, path: str) -> bool:
        """Check if a file was modified during this session.

        Args:
            path: Path to check.

        Returns:
            True if the file was modified in this session.
        """
        return any(m.path == path for m in self.modifications)

    def get_file_modifications(self, path: str) -> list[FileModification]:
        """Get all modifications to a specific file.

        Args:
            path: Path to get modifications for.

        Returns:
            List of modifications to the file, in chronological order.
        """
        return [m for m in self.modifications if m.path == path]

    def get_modification_summary(self, max_entries: int = 20) -> str:
        """Get a summary of all modifications in this session.

        Args:
            max_entries: Maximum number of modifications to include.

        Returns:
            Human-readable summary of modifications.
        """
        if not self.modifications:
            return "No file modifications in this session."

        lines = [f"File modifications ({len(self.modifications)} total):"]

        # Group by operation type
        by_operation: dict[str, list[str]] = {}
        for mod in self.modifications[-max_entries:]:
            op = mod.operation
            if op not in by_operation:
                by_operation[op] = []
            by_operation[op].append(mod.path)

        for operation, paths in by_operation.items():
            unique_paths = list(dict.fromkeys(paths))  # Preserve order, remove dupes
            lines.append(f"  {operation.capitalize()}d: {len(unique_paths)} file(s)")
            for path in unique_paths[:5]:  # Show first 5
                lines.append(f"    - {path}")
            if len(unique_paths) > 5:
                lines.append(f"    ... and {len(unique_paths) - 5} more")

        return "\n".join(lines)

    def get_recently_read_files(self, limit: int = 10) -> list[str]:
        """Get paths of recently read files.

        Args:
            limit: Maximum number of files to return.

        Returns:
            List of file paths, most recently read first.
        """
        sorted_records = sorted(
            self.read_files.values(),
            key=lambda r: r.timestamp,
            reverse=True,
        )
        return [r.path for r in sorted_records[:limit]]

    def get_recently_modified_files(self, limit: int = 10) -> list[str]:
        """Get paths of recently modified files.

        Args:
            limit: Maximum number of files to return.

        Returns:
            List of file paths, most recently modified first.
        """
        # Get unique paths from most recent modifications
        seen: set[str] = set()
        result: list[str] = []

        for mod in reversed(self.modifications):
            if mod.path not in seen:
                seen.add(mod.path)
                result.append(mod.path)
                if len(result) >= limit:
                    break

        return result

    def clear(self) -> None:
        """Clear all tracking data."""
        self.modifications.clear()
        self.read_files.clear()
        logger.debug(f"Cleared tool context for session {self.session_id}")


def compute_content_hash(content: str | bytes) -> str:
    """Compute a hash for file content.

    Args:
        content: File content as string or bytes.

    Returns:
        Hexadecimal hash string.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
