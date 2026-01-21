"""Tests for the tool context tracking module."""

import pytest
from datetime import datetime, timezone, timedelta

from codecrew.tools.context import (
    ToolContext,
    FileModification,
    FileReadRecord,
    compute_content_hash,
)


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_hash_string_content(self):
        """Should hash string content."""
        content = "Hello, World!"
        hash_result = compute_content_hash(content)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex length

    def test_hash_bytes_content(self):
        """Should hash bytes content."""
        content = b"Binary content"
        hash_result = compute_content_hash(content)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_same_content_same_hash(self):
        """Same content should produce same hash."""
        content = "Test content"
        assert compute_content_hash(content) == compute_content_hash(content)

    def test_different_content_different_hash(self):
        """Different content should produce different hash."""
        assert compute_content_hash("Content A") != compute_content_hash("Content B")


class TestFileModification:
    """Tests for FileModification dataclass."""

    def test_create_modification(self):
        """Should create a modification record."""
        mod = FileModification(
            path="/path/to/file.py",
            operation="write",
        )

        assert mod.path == "/path/to/file.py"
        assert mod.operation == "write"
        assert mod.timestamp is not None
        assert mod.content_hash is None
        assert mod.details is None

    def test_str_representation(self):
        """Should have readable string representation."""
        mod = FileModification(
            path="/path/to/file.py",
            operation="edit",
        )

        str_repr = str(mod)
        assert "edit" in str_repr
        assert "/path/to/file.py" in str_repr


class TestFileReadRecord:
    """Tests for FileReadRecord dataclass."""

    def test_create_read_record(self):
        """Should create a read record."""
        record = FileReadRecord(
            path="/path/to/file.py",
            content_hash="abc123",
        )

        assert record.path == "/path/to/file.py"
        assert record.content_hash == "abc123"
        assert record.timestamp is not None


class TestToolContext:
    """Tests for ToolContext class."""

    def test_create_context(self):
        """Should create a new context with session ID."""
        ctx = ToolContext()

        assert ctx.session_id is not None
        assert len(ctx.session_id) > 0
        assert len(ctx.modifications) == 0
        assert len(ctx.read_files) == 0

    def test_record_modification(self):
        """Should record file modifications."""
        ctx = ToolContext()
        ctx.record_modification("/path/file.py", "write")

        assert len(ctx.modifications) == 1
        assert ctx.modifications[0].path == "/path/file.py"
        assert ctx.modifications[0].operation == "write"

    def test_record_modification_with_hash(self):
        """Should record modification with content hash."""
        ctx = ToolContext()
        ctx.record_modification(
            "/path/file.py",
            "edit",
            content_hash="abc123",
            details="Added function",
        )

        mod = ctx.modifications[0]
        assert mod.content_hash == "abc123"
        assert mod.details == "Added function"

    def test_record_read(self):
        """Should record file reads."""
        ctx = ToolContext()
        ctx.record_read("/path/file.py", "hash123")

        assert "/path/file.py" in ctx.read_files
        assert ctx.read_files["/path/file.py"].content_hash == "hash123"

    def test_record_read_updates_existing(self):
        """Recording read of same file should update record."""
        ctx = ToolContext()
        ctx.record_read("/path/file.py", "hash1")
        ctx.record_read("/path/file.py", "hash2")

        assert ctx.read_files["/path/file.py"].content_hash == "hash2"

    def test_is_file_stale_never_read(self):
        """File never read should not be stale."""
        ctx = ToolContext()

        assert ctx.is_file_stale("/path/file.py", "any_hash") is False

    def test_is_file_stale_unchanged(self):
        """File with same hash should not be stale."""
        ctx = ToolContext()
        ctx.record_read("/path/file.py", "same_hash")

        assert ctx.is_file_stale("/path/file.py", "same_hash") is False

    def test_is_file_stale_changed(self):
        """File with different hash should be stale."""
        ctx = ToolContext()
        ctx.record_read("/path/file.py", "old_hash")

        assert ctx.is_file_stale("/path/file.py", "new_hash") is True

    def test_was_file_modified(self):
        """Should detect if file was modified in session."""
        ctx = ToolContext()
        ctx.record_modification("/path/file.py", "write")

        assert ctx.was_file_modified("/path/file.py") is True
        assert ctx.was_file_modified("/other/file.py") is False

    def test_get_file_modifications(self):
        """Should get all modifications for a specific file."""
        ctx = ToolContext()
        ctx.record_modification("/path/file1.py", "write")
        ctx.record_modification("/path/file2.py", "write")
        ctx.record_modification("/path/file1.py", "edit")

        mods = ctx.get_file_modifications("/path/file1.py")
        assert len(mods) == 2
        assert mods[0].operation == "write"
        assert mods[1].operation == "edit"

    def test_get_modification_summary_empty(self):
        """Should handle empty modifications."""
        ctx = ToolContext()
        summary = ctx.get_modification_summary()

        assert "No file modifications" in summary

    def test_get_modification_summary_with_mods(self):
        """Should summarize modifications by operation type."""
        ctx = ToolContext()
        ctx.record_modification("/path/file1.py", "write")
        ctx.record_modification("/path/file2.py", "write")
        ctx.record_modification("/path/file3.py", "edit")

        summary = ctx.get_modification_summary()

        assert "Write" in summary or "write" in summary.lower()
        assert "Edit" in summary or "edit" in summary.lower()

    def test_get_recently_read_files(self):
        """Should return recently read files."""
        ctx = ToolContext()
        ctx.record_read("/path/file1.py", "hash1")
        ctx.record_read("/path/file2.py", "hash2")
        ctx.record_read("/path/file3.py", "hash3")

        recent = ctx.get_recently_read_files(limit=2)
        assert len(recent) == 2

    def test_get_recently_modified_files(self):
        """Should return recently modified files (unique)."""
        ctx = ToolContext()
        ctx.record_modification("/path/file1.py", "write")
        ctx.record_modification("/path/file2.py", "write")
        ctx.record_modification("/path/file1.py", "edit")  # Same file again

        recent = ctx.get_recently_modified_files(limit=10)
        # file1 should appear once, most recently
        assert "/path/file1.py" in recent
        assert "/path/file2.py" in recent
        assert len(recent) == 2

    def test_clear(self):
        """Should clear all tracking data."""
        ctx = ToolContext()
        ctx.record_modification("/path/file.py", "write")
        ctx.record_read("/path/file.py", "hash")

        ctx.clear()

        assert len(ctx.modifications) == 0
        assert len(ctx.read_files) == 0


class TestToolContextIntegration:
    """Integration tests for ToolContext."""

    def test_typical_workflow(self):
        """Test a typical read-modify-check workflow."""
        ctx = ToolContext()

        # Read a file
        original_content = "def foo(): pass"
        original_hash = compute_content_hash(original_content)
        ctx.record_read("/project/main.py", original_hash)

        # Modify it
        ctx.record_modification("/project/main.py", "edit")

        # New content has different hash
        new_content = "def foo(): return 42"
        new_hash = compute_content_hash(new_content)

        # File should be detected as stale
        assert ctx.is_file_stale("/project/main.py", new_hash) is True

        # Re-read with new hash
        ctx.record_read("/project/main.py", new_hash)

        # No longer stale
        assert ctx.is_file_stale("/project/main.py", new_hash) is False
