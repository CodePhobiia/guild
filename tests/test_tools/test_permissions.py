"""Tests for the permission system."""

import pytest

from codecrew.tools.permissions import (
    PermissionDeniedError,
    PermissionLevel,
    PermissionManager,
    PermissionRequest,
)


class TestPermissionLevel:
    """Tests for PermissionLevel enum."""

    def test_level_values(self):
        """Test permission level values."""
        assert PermissionLevel.SAFE.value == "safe"
        assert PermissionLevel.CAUTIOUS.value == "cautious"
        assert PermissionLevel.DANGEROUS.value == "dangerous"
        assert PermissionLevel.BLOCKED.value == "blocked"

    def test_requires_confirmation(self):
        """Test which levels require confirmation."""
        assert not PermissionLevel.SAFE.requires_confirmation()
        assert PermissionLevel.CAUTIOUS.requires_confirmation()
        assert PermissionLevel.DANGEROUS.requires_confirmation()
        assert not PermissionLevel.BLOCKED.requires_confirmation()

    def test_level_comparison(self):
        """Test permission level comparison."""
        assert PermissionLevel.SAFE < PermissionLevel.CAUTIOUS
        assert PermissionLevel.CAUTIOUS < PermissionLevel.DANGEROUS
        assert PermissionLevel.DANGEROUS < PermissionLevel.BLOCKED

        assert PermissionLevel.SAFE <= PermissionLevel.SAFE
        assert PermissionLevel.SAFE <= PermissionLevel.CAUTIOUS


class TestPermissionRequest:
    """Tests for PermissionRequest dataclass."""

    def test_create_request(self):
        """Test creating a permission request."""
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "/tmp/test.txt", "content": "Hello"},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write content to a file",
        )

        assert request.tool_name == "write_file"
        assert request.arguments == {"path": "/tmp/test.txt", "content": "Hello"}
        assert request.permission_level == PermissionLevel.CAUTIOUS
        assert request.description == "Write content to a file"
        assert request.timestamp is not None

    def test_format_for_display(self):
        """Test formatting request for display."""
        request = PermissionRequest(
            tool_name="write_file",
            arguments={"path": "/tmp/test.txt", "content": "Hello"},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write content to a file",
        )

        display = request.format_for_display()

        assert "write_file" in display
        assert "cautious" in display
        assert "Write content to a file" in display
        assert "path" in display
        assert "/tmp/test.txt" in display

    def test_format_truncates_long_values(self):
        """Test that long values are truncated in display."""
        long_content = "x" * 200

        request = PermissionRequest(
            tool_name="test",
            arguments={"content": long_content},
            permission_level=PermissionLevel.SAFE,
            description="Test",
        )

        display = request.format_for_display()
        assert "..." in display


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_error_message(self):
        """Test error message formatting."""
        error = PermissionDeniedError(
            tool_name="dangerous_tool",
            reason="User denied",
            required_level=PermissionLevel.DANGEROUS,
        )

        assert "dangerous_tool" in str(error)
        assert "User denied" in str(error)
        assert error.tool_name == "dangerous_tool"
        assert error.reason == "User denied"
        assert error.required_level == PermissionLevel.DANGEROUS


class TestPermissionManager:
    """Tests for PermissionManager."""

    def test_auto_approve_mode(self):
        """Test auto-approve mode grants all permissions."""
        manager = PermissionManager(auto_approve=True)

        result = manager.check_permission(
            tool_name="dangerous_tool",
            arguments={},
            permission_level=PermissionLevel.DANGEROUS,
            description="Dangerous operation",
        )

        assert result is True

    def test_safe_level_auto_approved(self):
        """Test SAFE level is auto-approved without callback."""
        manager = PermissionManager()

        result = manager.check_permission(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
            permission_level=PermissionLevel.SAFE,
            description="Read file",
        )

        assert result is True

    def test_cautious_level_denied_without_callback(self):
        """Test CAUTIOUS level is denied without confirmation callback."""
        manager = PermissionManager()

        result = manager.check_permission(
            tool_name="write_file",
            arguments={"path": "/tmp/test.txt"},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )

        assert result is False

    def test_confirmation_callback_called(self):
        """Test confirmation callback is called for cautious operations."""
        callback_calls = []

        def callback(request):
            callback_calls.append(request)
            return True

        manager = PermissionManager()
        manager.set_confirmation_callback(callback)

        result = manager.check_permission(
            tool_name="write_file",
            arguments={"path": "/tmp/test.txt"},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )

        assert result is True
        assert len(callback_calls) == 1
        assert callback_calls[0].tool_name == "write_file"

    def test_confirmation_denied(self):
        """Test that denied confirmation returns False."""
        manager = PermissionManager()
        manager.set_confirmation_callback(lambda req: False)

        result = manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )

        assert result is False

    def test_block_tool(self):
        """Test blocking a tool."""
        manager = PermissionManager()

        manager.block_tool("dangerous_tool")

        with pytest.raises(PermissionDeniedError, match="blocked"):
            manager.check_permission(
                tool_name="dangerous_tool",
                arguments={},
                permission_level=PermissionLevel.SAFE,
                description="Dangerous operation",
            )

    def test_unblock_tool(self):
        """Test unblocking a tool."""
        manager = PermissionManager()

        manager.block_tool("dangerous_tool")
        assert manager.is_blocked("dangerous_tool")

        manager.unblock_tool("dangerous_tool")
        assert not manager.is_blocked("dangerous_tool")

    def test_session_grants(self):
        """Test session permission grants."""
        callback_calls = []

        def callback(request):
            callback_calls.append(request)
            return True

        manager = PermissionManager()
        manager.set_confirmation_callback(callback)

        # First call should trigger callback
        result1 = manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )
        assert result1 is True
        assert len(callback_calls) == 1

        # Second call should use session grant (no callback)
        result2 = manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )
        assert result2 is True
        assert len(callback_calls) == 1  # Still 1, not called again

    def test_clear_session_grants(self):
        """Test clearing session grants."""
        manager = PermissionManager()
        manager.set_confirmation_callback(lambda req: True)

        manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )

        assert manager.has_session_permission("write_file")

        manager.clear_session_grants()

        assert not manager.has_session_permission("write_file")

    def test_tool_permission_override(self):
        """Test overriding permission level for specific tool."""
        manager = PermissionManager()

        # Normally DANGEROUS requires confirmation
        manager.set_tool_permission("dangerous_tool", PermissionLevel.SAFE)

        result = manager.check_permission(
            tool_name="dangerous_tool",
            arguments={},
            permission_level=PermissionLevel.DANGEROUS,
            description="Dangerous operation",
        )

        assert result is True  # Auto-approved because effective level is SAFE

    def test_clear_tool_permission(self):
        """Test clearing a tool permission override."""
        manager = PermissionManager()

        manager.set_tool_permission("test_tool", PermissionLevel.SAFE)
        manager.clear_tool_permission("test_tool")

        # Effective level should now be the default
        effective = manager.get_effective_level("test_tool", PermissionLevel.CAUTIOUS)
        assert effective == PermissionLevel.CAUTIOUS

    def test_list_blocked_tools(self):
        """Test listing blocked tools."""
        manager = PermissionManager()

        manager.block_tool("tool1")
        manager.block_tool("tool2")

        blocked = manager.list_blocked_tools()
        assert sorted(blocked) == ["tool1", "tool2"]

    def test_list_session_grants(self):
        """Test listing session grants."""
        manager = PermissionManager()
        manager.set_confirmation_callback(lambda req: True)

        manager.check_permission(
            "tool1", {}, PermissionLevel.CAUTIOUS, "Tool 1"
        )
        manager.check_permission(
            "tool2", {}, PermissionLevel.CAUTIOUS, "Tool 2"
        )

        grants = manager.list_session_grants()
        assert sorted(grants) == ["tool1", "tool2"]

    def test_list_overrides(self):
        """Test listing permission overrides."""
        manager = PermissionManager()

        manager.set_tool_permission("tool1", PermissionLevel.SAFE)
        manager.set_tool_permission("tool2", PermissionLevel.BLOCKED)

        overrides = manager.list_overrides()
        assert overrides == {
            "tool1": PermissionLevel.SAFE,
            "tool2": PermissionLevel.BLOCKED,
        }

    def test_skip_confirmation_when_not_required(self):
        """Test that confirmation can be skipped."""
        callback_calls = []
        manager = PermissionManager()
        manager.set_confirmation_callback(lambda req: callback_calls.append(req) or True)

        result = manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
            require_confirmation=False,
        )

        assert result is True
        assert len(callback_calls) == 0  # Callback not called

    def test_auto_approve_level_threshold(self):
        """Test auto-approve level threshold."""
        manager = PermissionManager(auto_approve_level=PermissionLevel.CAUTIOUS)

        # CAUTIOUS should be auto-approved
        result = manager.check_permission(
            tool_name="write_file",
            arguments={},
            permission_level=PermissionLevel.CAUTIOUS,
            description="Write file",
        )
        assert result is True

        # DANGEROUS should still require confirmation
        result2 = manager.check_permission(
            tool_name="dangerous_tool",
            arguments={},
            permission_level=PermissionLevel.DANGEROUS,
            description="Dangerous",
        )
        assert result2 is False  # No callback set
