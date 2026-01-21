"""Cross-platform clipboard operations for the TUI."""

import subprocess
import sys
from typing import Optional


class ClipboardError(Exception):
    """Exception raised when clipboard operations fail."""

    pass


class ClipboardManager:
    """Cross-platform clipboard operations.

    Provides copy/paste functionality that works across
    Windows, macOS, and Linux (with xclip or xsel).
    """

    @staticmethod
    def is_available() -> bool:
        """Check if clipboard operations are available.

        Returns:
            True if clipboard is available, False otherwise
        """
        try:
            ClipboardManager._get_copy_command()
            return True
        except ClipboardError:
            return False

    @staticmethod
    def _get_copy_command() -> list[str]:
        """Get the system-specific copy command.

        Returns:
            Command list for copying to clipboard

        Raises:
            ClipboardError: If no clipboard command is available
        """
        if sys.platform == "win32":
            return ["clip"]
        elif sys.platform == "darwin":
            return ["pbcopy"]
        else:
            # Linux - try xclip first, then xsel
            try:
                subprocess.run(
                    ["which", "xclip"],
                    check=True,
                    capture_output=True,
                )
                return ["xclip", "-selection", "clipboard"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            try:
                subprocess.run(
                    ["which", "xsel"],
                    check=True,
                    capture_output=True,
                )
                return ["xsel", "--clipboard", "--input"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            raise ClipboardError(
                "No clipboard command available. "
                "Install xclip or xsel on Linux."
            )

    @staticmethod
    def _get_paste_command() -> list[str]:
        """Get the system-specific paste command.

        Returns:
            Command list for pasting from clipboard

        Raises:
            ClipboardError: If no clipboard command is available
        """
        if sys.platform == "win32":
            return ["powershell", "-command", "Get-Clipboard"]
        elif sys.platform == "darwin":
            return ["pbpaste"]
        else:
            # Linux - try xclip first, then xsel
            try:
                subprocess.run(
                    ["which", "xclip"],
                    check=True,
                    capture_output=True,
                )
                return ["xclip", "-selection", "clipboard", "-o"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            try:
                subprocess.run(
                    ["which", "xsel"],
                    check=True,
                    capture_output=True,
                )
                return ["xsel", "--clipboard", "--output"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            raise ClipboardError(
                "No clipboard command available. "
                "Install xclip or xsel on Linux."
            )

    @staticmethod
    def copy(text: str) -> bool:
        """Copy text to the clipboard.

        Args:
            text: Text to copy to clipboard

        Returns:
            True if copy succeeded, False otherwise
        """
        if not text:
            return False

        try:
            cmd = ClipboardManager._get_copy_command()
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0
        except (ClipboardError, FileNotFoundError, OSError):
            return False

    @staticmethod
    def paste() -> Optional[str]:
        """Get text from the clipboard.

        Returns:
            Clipboard text or None if paste failed
        """
        try:
            cmd = ClipboardManager._get_paste_command()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except (ClipboardError, FileNotFoundError, OSError):
            return None

    @staticmethod
    def copy_message(content: str, role: Optional[str] = None) -> bool:
        """Copy a message to clipboard with optional role prefix.

        Args:
            content: Message content to copy
            role: Optional role to prefix (e.g., "assistant", "user")

        Returns:
            True if copy succeeded, False otherwise
        """
        if role:
            text = f"[{role}]: {content}"
        else:
            text = content

        return ClipboardManager.copy(text)

    @staticmethod
    def copy_code_block(code: str, language: Optional[str] = None) -> bool:
        """Copy a code block to clipboard.

        Args:
            code: Code content to copy
            language: Optional language for markdown formatting

        Returns:
            True if copy succeeded, False otherwise
        """
        if language:
            text = f"```{language}\n{code}\n```"
        else:
            text = code

        return ClipboardManager.copy(text)

    @staticmethod
    def copy_conversation(
        messages: list[tuple[str, str]],
        include_roles: bool = True,
    ) -> bool:
        """Copy multiple messages as a conversation.

        Args:
            messages: List of (role, content) tuples
            include_roles: Whether to include role prefixes

        Returns:
            True if copy succeeded, False otherwise
        """
        lines = []
        for role, content in messages:
            if include_roles:
                lines.append(f"[{role}]: {content}")
            else:
                lines.append(content)
            lines.append("")  # Blank line between messages

        return ClipboardManager.copy("\n".join(lines).strip())


def copy_to_clipboard(text: str) -> bool:
    """Convenience function to copy text to clipboard.

    Args:
        text: Text to copy

    Returns:
        True if successful, False otherwise
    """
    return ClipboardManager.copy(text)


def paste_from_clipboard() -> Optional[str]:
    """Convenience function to paste from clipboard.

    Returns:
        Clipboard text or None if paste failed
    """
    return ClipboardManager.paste()


def clipboard_available() -> bool:
    """Convenience function to check clipboard availability.

    Returns:
        True if clipboard operations are available
    """
    return ClipboardManager.is_available()
