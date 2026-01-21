"""Tests for the clipboard module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from codecrew.ui.clipboard import (
    ClipboardError,
    ClipboardManager,
    clipboard_available,
    copy_to_clipboard,
    paste_from_clipboard,
)


class TestClipboardManager:
    """Tests for ClipboardManager class."""

    def test_is_available_returns_bool(self):
        """Test that is_available returns a boolean."""
        result = ClipboardManager.is_available()
        assert isinstance(result, bool)

    @patch("subprocess.Popen")
    def test_copy_success(self, mock_popen):
        """Test successful copy operation."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = ClipboardManager.copy("test text")
        assert result is True

    @patch("subprocess.Popen")
    def test_copy_failure(self, mock_popen):
        """Test failed copy operation."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        result = ClipboardManager.copy("test text")
        assert result is False

    def test_copy_empty_text(self):
        """Test copying empty text returns False."""
        result = ClipboardManager.copy("")
        assert result is False

    @patch("subprocess.run")
    def test_paste_success(self, mock_run):
        """Test successful paste operation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="clipboard content",
        )

        result = ClipboardManager.paste()
        assert result == "clipboard content"

    @patch("subprocess.run")
    def test_paste_failure(self, mock_run):
        """Test failed paste operation."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = ClipboardManager.paste()
        assert result is None

    def test_copy_message_with_role(self):
        """Test copying message with role prefix."""
        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_message("Hello!", role="user")
            assert result is True
            mock_copy.assert_called_once_with("[user]: Hello!")

    def test_copy_message_without_role(self):
        """Test copying message without role prefix."""
        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_message("Hello!")
            assert result is True
            mock_copy.assert_called_once_with("Hello!")

    def test_copy_code_block_with_language(self):
        """Test copying code block with language."""
        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_code_block("print('hello')", language="python")
            assert result is True
            mock_copy.assert_called_once_with("```python\nprint('hello')\n```")

    def test_copy_code_block_without_language(self):
        """Test copying code block without language."""
        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_code_block("print('hello')")
            assert result is True
            mock_copy.assert_called_once_with("print('hello')")

    def test_copy_conversation(self):
        """Test copying conversation."""
        messages = [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
        ]

        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_conversation(messages)
            assert result is True
            expected = "[user]: Hello\n\n[assistant]: Hi there!"
            mock_copy.assert_called_once_with(expected)

    def test_copy_conversation_without_roles(self):
        """Test copying conversation without roles."""
        messages = [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
        ]

        with patch.object(ClipboardManager, "copy", return_value=True) as mock_copy:
            result = ClipboardManager.copy_conversation(messages, include_roles=False)
            assert result is True
            expected = "Hello\n\nHi there!"
            mock_copy.assert_called_once_with(expected)


class TestCopyCommand:
    """Tests for _get_copy_command method."""

    @patch.object(sys, "platform", "win32")
    def test_get_copy_command_windows(self):
        """Test copy command on Windows."""
        cmd = ClipboardManager._get_copy_command()
        assert cmd == ["clip"]

    @patch.object(sys, "platform", "darwin")
    def test_get_copy_command_macos(self):
        """Test copy command on macOS."""
        cmd = ClipboardManager._get_copy_command()
        assert cmd == ["pbcopy"]

    @patch.object(sys, "platform", "linux")
    @patch("subprocess.run")
    def test_get_copy_command_linux_xclip(self, mock_run):
        """Test copy command on Linux with xclip."""
        mock_run.return_value = MagicMock(returncode=0)

        cmd = ClipboardManager._get_copy_command()
        assert cmd == ["xclip", "-selection", "clipboard"]

    @patch.object(sys, "platform", "linux")
    @patch("subprocess.run")
    def test_get_copy_command_linux_xsel(self, mock_run):
        """Test copy command on Linux with xsel (fallback)."""
        from subprocess import CalledProcessError

        # First call raises (xclip not found), second succeeds (xsel)
        mock_run.side_effect = [
            CalledProcessError(1, "which"),  # xclip not found
            MagicMock(returncode=0),  # xsel found
        ]

        cmd = ClipboardManager._get_copy_command()
        assert cmd == ["xsel", "--clipboard", "--input"]

    @patch.object(sys, "platform", "linux")
    @patch("subprocess.run")
    def test_get_copy_command_linux_no_clipboard(self, mock_run):
        """Test copy command on Linux without clipboard tools."""
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "which")

        with pytest.raises(ClipboardError):
            ClipboardManager._get_copy_command()


class TestPasteCommand:
    """Tests for _get_paste_command method."""

    @patch.object(sys, "platform", "win32")
    def test_get_paste_command_windows(self):
        """Test paste command on Windows."""
        cmd = ClipboardManager._get_paste_command()
        assert cmd == ["powershell", "-command", "Get-Clipboard"]

    @patch.object(sys, "platform", "darwin")
    def test_get_paste_command_macos(self):
        """Test paste command on macOS."""
        cmd = ClipboardManager._get_paste_command()
        assert cmd == ["pbpaste"]

    @patch.object(sys, "platform", "linux")
    @patch("subprocess.run")
    def test_get_paste_command_linux_xclip(self, mock_run):
        """Test paste command on Linux with xclip."""
        mock_run.return_value = MagicMock(returncode=0)

        cmd = ClipboardManager._get_paste_command()
        assert cmd == ["xclip", "-selection", "clipboard", "-o"]


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_copy_to_clipboard(self):
        """Test copy_to_clipboard convenience function."""
        with patch.object(ClipboardManager, "copy", return_value=True) as mock:
            result = copy_to_clipboard("test")
            assert result is True
            mock.assert_called_once_with("test")

    def test_paste_from_clipboard(self):
        """Test paste_from_clipboard convenience function."""
        with patch.object(ClipboardManager, "paste", return_value="text") as mock:
            result = paste_from_clipboard()
            assert result == "text"
            mock.assert_called_once()

    def test_clipboard_available(self):
        """Test clipboard_available convenience function."""
        with patch.object(ClipboardManager, "is_available", return_value=True) as mock:
            result = clipboard_available()
            assert result is True
            mock.assert_called_once()


class TestClipboardError:
    """Tests for ClipboardError exception."""

    def test_clipboard_error_message(self):
        """Test ClipboardError with message."""
        error = ClipboardError("No clipboard available")
        assert str(error) == "No clipboard available"

    def test_clipboard_error_is_exception(self):
        """Test that ClipboardError is an Exception."""
        assert issubclass(ClipboardError, Exception)
