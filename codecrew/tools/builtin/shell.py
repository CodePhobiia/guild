"""Shell command execution tool for CodeCrew.

This tool provides safe shell command execution with timeout protection,
output capture, and appropriate permission levels.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from codecrew.models.tools import EXECUTE_COMMAND_TOOL, ToolDefinition, ToolParameter
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool

logger = logging.getLogger(__name__)

# Commands that are considered dangerous and require extra confirmation
DANGEROUS_COMMANDS = {
    # File system destructive operations
    "rm",
    "rmdir",
    "del",
    "rd",
    "format",
    "mkfs",
    # System modification
    "chmod",
    "chown",
    "chattr",
    "sudo",
    "su",
    "doas",
    # Package management (can modify system)
    "apt",
    "apt-get",
    "yum",
    "dnf",
    "pacman",
    "brew",
    "pip",
    "npm",
    "yarn",
    "pnpm",
    # Network/remote operations
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "ftp",
    "sftp",
    # Process control
    "kill",
    "killall",
    "pkill",
    # Disk operations
    "dd",
    "fdisk",
    "parted",
    "mount",
    "umount",
    # Git destructive operations
    "git push",
    "git reset",
    "git rebase",
    "git merge",
    # Database operations
    "mysql",
    "psql",
    "mongo",
    "redis-cli",
}

# Commands that are always blocked
BLOCKED_COMMANDS = {
    # Extremely dangerous
    "rm -rf /",
    "rm -rf /*",
    ":(){ :|:& };:",  # Fork bomb
    "> /dev/sda",
    "mkfs.ext4 /dev/sda",
    # Credential exposure
    "cat /etc/shadow",
    "cat /etc/passwd",
}


def _get_command_base(command: str) -> str:
    """Extract the base command from a command string.

    Args:
        command: Full command string.

    Returns:
        The base command (first word or first two words for git/docker).
    """
    parts = command.strip().split()
    if not parts:
        return ""

    base = parts[0].lower()

    # For compound commands like "git push", include second word
    if base in ("git", "docker", "kubectl") and len(parts) > 1:
        return f"{base} {parts[1].lower()}"

    return base


def _is_command_blocked(command: str) -> bool:
    """Check if a command is in the blocked list.

    Args:
        command: Command to check.

    Returns:
        True if command is blocked.
    """
    normalized = command.strip().lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in normalized:
            return True
    return False


def _is_command_dangerous(command: str) -> bool:
    """Check if a command is considered dangerous.

    Args:
        command: Command to check.

    Returns:
        True if command requires extra caution.
    """
    base = _get_command_base(command)

    # Check for exact match
    if base in DANGEROUS_COMMANDS:
        return True

    # Check for partial match (e.g., "git push" when base is "git")
    for dangerous in DANGEROUS_COMMANDS:
        if command.strip().lower().startswith(dangerous):
            return True

    # Check for pipe to dangerous commands
    if "|" in command:
        for part in command.split("|"):
            if _is_command_dangerous(part.strip()):
                return True

    # Check for command chaining with dangerous commands
    for sep in ("&&", "||", ";"):
        if sep in command:
            for part in command.split(sep):
                if _is_command_dangerous(part.strip()):
                    return True

    return False


def create_execute_command_tool(
    working_directory: str | None = None,
    timeout: float = 60.0,
    max_output_length: int = 50000,
    shell: bool = True,
) -> Tool:
    """Create a tool for executing shell commands.

    Args:
        working_directory: Default working directory for commands.
        timeout: Maximum execution time in seconds.
        max_output_length: Maximum characters to capture from output.
        shell: If True, execute through shell (enables pipes, etc.).

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        command = args["command"]
        cwd = args.get("cwd")

        # Resolve working directory
        if cwd:
            work_dir = Path(cwd)
            if not work_dir.is_absolute():
                base = (
                    Path(working_directory) if working_directory else Path.cwd()
                )
                work_dir = base / work_dir
        else:
            work_dir = (
                Path(working_directory) if working_directory else Path.cwd()
            )

        work_dir = work_dir.resolve()

        if not work_dir.exists():
            raise FileNotFoundError(f"Working directory not found: {work_dir}")

        if not work_dir.is_dir():
            raise ValueError(f"Path is not a directory: {work_dir}")

        # Security check
        if _is_command_blocked(command):
            raise PermissionError(f"Command is blocked for security: {command}")

        logger.info(f"Executing command: {command} (in {work_dir})")

        try:
            # Execute the command
            if shell:
                # Use shell=True for shell features (pipes, etc.)
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
            else:
                # Parse command for non-shell execution
                if sys.platform == "win32":
                    cmd_parts = command.split()
                else:
                    cmd_parts = shlex.split(command)

                result = subprocess.run(
                    cmd_parts,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )

            # Build output
            output_parts = []

            if result.stdout:
                stdout = result.stdout
                if len(stdout) > max_output_length:
                    stdout = (
                        stdout[:max_output_length]
                        + f"\n... (stdout truncated at {max_output_length} chars)"
                    )
                output_parts.append(f"STDOUT:\n{stdout}")

            if result.stderr:
                stderr = result.stderr
                if len(stderr) > max_output_length:
                    stderr = (
                        stderr[:max_output_length]
                        + f"\n... (stderr truncated at {max_output_length} chars)"
                    )
                output_parts.append(f"STDERR:\n{stderr}")

            output_parts.append(f"Exit code: {result.returncode}")

            output = "\n\n".join(output_parts)

            if result.returncode != 0:
                logger.warning(
                    f"Command exited with code {result.returncode}: {command}"
                )
            else:
                logger.debug(f"Command completed successfully: {command}")

            return output

        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Command timed out after {timeout} seconds: {command}"
            )

    # Determine permission level based on command analysis
    # The actual permission level will be checked at runtime based on the specific command
    # But we set DANGEROUS as default to ensure confirmation is requested
    return Tool(
        definition=EXECUTE_COMMAND_TOOL,
        handler=handler,
        permission_level=PermissionLevel.DANGEROUS,
        category="shell",
        description="Execute a shell command",
        timeout=timeout + 5.0,  # Add buffer for process overhead
    )


def get_command_permission_level(command: str) -> PermissionLevel:
    """Get the appropriate permission level for a command.

    This can be used to dynamically adjust permission level based
    on the specific command being executed.

    Args:
        command: The command to analyze.

    Returns:
        Appropriate PermissionLevel for the command.
    """
    if _is_command_blocked(command):
        return PermissionLevel.BLOCKED

    if _is_command_dangerous(command):
        return PermissionLevel.DANGEROUS

    # Read-only commands are safer
    read_only_commands = {
        "ls",
        "dir",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "find",
        "which",
        "where",
        "whoami",
        "pwd",
        "echo",
        "env",
        "printenv",
        "date",
        "cal",
        "wc",
        "diff",
        "file",
        "stat",
        "tree",
        "git status",
        "git log",
        "git diff",
        "git branch",
        "git show",
    }

    base = _get_command_base(command)
    if base in read_only_commands:
        return PermissionLevel.SAFE

    # Default to cautious for unknown commands
    return PermissionLevel.CAUTIOUS
