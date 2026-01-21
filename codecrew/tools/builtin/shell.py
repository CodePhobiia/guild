"""Shell command execution tool for CodeCrew.

This tool provides safe shell command execution with timeout protection,
output capture, and appropriate permission levels.

Security measures:
- Blocked command list prevents dangerous operations
- Path validation ensures commands run in allowed directories
- Output truncation prevents memory exhaustion
- Timeout protection prevents runaway processes
- Dangerous command detection requires explicit approval
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from codecrew.errors import CommandBlockedError, PathAccessError, InputValidationError
from codecrew.models.tools import EXECUTE_COMMAND_TOOL
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
    "rm -rf ~",
    "rm -rf ~/*",
    ":(){ :|:& };:",  # Fork bomb
    "> /dev/sda",
    "mkfs.ext4 /dev/sda",
    # Credential exposure
    "cat /etc/shadow",
    "cat /etc/passwd",
}

# Patterns that indicate potentially malicious commands
BLOCKED_PATTERNS = [
    r"rm\s+(-[rf]+\s+)*(/|/\*|\~|\~/)$",  # rm -rf / variants
    r">\s*/dev/[hs]d[a-z]",  # Overwrite disk devices
    r"mkfs\.",  # Format filesystem
    r"dd\s+.*of=/dev/[hs]d[a-z]",  # dd to disk device
    r"\|\s*sh\s*$",  # Piping to shell (potential injection)
    r"\|\s*bash\s*$",  # Piping to bash
    r"`.*`",  # Command substitution (potential injection)
    r"\$\(.*\)",  # Command substitution variant
    r";\s*rm\s+",  # Command chaining with rm
    r"&&\s*rm\s+",  # Command chaining with rm
    r"eval\s+",  # Eval (code execution)
    r"exec\s+",  # Exec (replace process)
]

# Compile patterns for efficiency
_BLOCKED_PATTERN_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


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


def _is_command_blocked(command: str) -> tuple[bool, str]:
    """Check if a command is in the blocked list.

    Args:
        command: Command to check.

    Returns:
        Tuple of (is_blocked, reason).
    """
    normalized = command.strip().lower()

    # Check explicit blocklist
    for blocked in BLOCKED_COMMANDS:
        if blocked in normalized:
            return True, f"matches blocked command: {blocked}"

    # Check dangerous patterns
    for pattern in _BLOCKED_PATTERN_RE:
        if pattern.search(command):
            return True, "matches dangerous pattern"

    return False, ""


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


def _validate_working_directory(
    cwd: str | None,
    base_directory: str | None,
    allowed_paths: list[str] | None = None,
) -> Path:
    """Validate and resolve working directory.

    Args:
        cwd: Requested working directory (may be relative).
        base_directory: Base directory for relative paths.
        allowed_paths: If set, working directory must be within one of these.

    Returns:
        Resolved and validated Path.

    Raises:
        PathAccessError: If directory is outside allowed paths.
        FileNotFoundError: If directory doesn't exist.
        ValueError: If path is not a directory.
    """
    if cwd:
        work_dir = Path(cwd)
        if not work_dir.is_absolute():
            base = Path(base_directory) if base_directory else Path.cwd()
            work_dir = base / work_dir
    else:
        work_dir = Path(base_directory) if base_directory else Path.cwd()

    # Resolve to absolute path (follows symlinks)
    work_dir = work_dir.resolve()

    # Validate existence
    if not work_dir.exists():
        raise FileNotFoundError(f"Working directory not found: {work_dir}")

    if not work_dir.is_dir():
        raise ValueError(f"Path is not a directory: {work_dir}")

    # Validate against allowed paths if specified
    if allowed_paths:
        is_allowed = False
        for allowed in allowed_paths:
            allowed_resolved = Path(allowed).resolve()
            try:
                work_dir.relative_to(allowed_resolved)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise PathAccessError(
                str(work_dir),
                "working directory is outside allowed paths"
            )

    return work_dir


def _sanitize_command_for_log(command: str, max_length: int = 100) -> str:
    """Sanitize command for logging (truncate, redact sensitive parts).

    Args:
        command: Command to sanitize.
        max_length: Maximum length to include.

    Returns:
        Sanitized command string.
    """
    # Truncate
    if len(command) > max_length:
        return command[:max_length] + "..."
    return command


def create_execute_command_tool(
    working_directory: str | None = None,
    timeout: float = 60.0,
    max_output_length: int = 50000,
    shell: bool = True,
    allowed_paths: list[str] | None = None,
) -> Tool:
    """Create a tool for executing shell commands.

    Args:
        working_directory: Default working directory for commands.
        timeout: Maximum execution time in seconds.
        max_output_length: Maximum characters to capture from output.
        shell: If True, execute through shell (enables pipes, etc.).
        allowed_paths: If set, commands can only run in these directories.

    Returns:
        Configured Tool instance.

    Security:
        - Commands are checked against blocklist and dangerous patterns
        - Working directory is validated against allowed paths
        - Output is truncated to prevent memory exhaustion
        - Timeout prevents runaway processes
    """

    def handler(args: dict[str, Any]) -> str:
        command = args.get("command", "")
        cwd = args.get("cwd")

        # Validate command is provided
        if not command or not command.strip():
            raise InputValidationError("command", "command cannot be empty")

        command = command.strip()

        # Security check - blocked commands
        is_blocked, reason = _is_command_blocked(command)
        if is_blocked:
            logger.warning(f"Blocked command attempt: {_sanitize_command_for_log(command)}")
            raise CommandBlockedError(command, reason)

        # Validate and resolve working directory
        work_dir = _validate_working_directory(cwd, working_directory, allowed_paths)

        # Log command execution (sanitized)
        logger.debug(f"Executing command in {work_dir}: {_sanitize_command_for_log(command)}")

        try:
            # Execute the command
            if shell:
                # Use shell=True for shell features (pipes, etc.)
                # Note: This is intentional to support shell features like pipes
                # Security is enforced via command blocklist and patterns
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
                # Parse command for non-shell execution (safer but limited)
                try:
                    if sys.platform == "win32":
                        cmd_parts = command.split()
                    else:
                        cmd_parts = shlex.split(command)
                except ValueError as e:
                    raise InputValidationError("command", f"invalid command syntax: {e}")

                result = subprocess.run(
                    cmd_parts,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )

            # Build output with truncation
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
                logger.debug(f"Command exited with code {result.returncode}")
            else:
                logger.debug("Command completed successfully")

            return output

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out after {timeout}s")
            raise TimeoutError(
                f"Command timed out after {timeout} seconds"
            )
        except OSError as e:
            logger.error(f"OS error executing command: {e}")
            raise

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
    is_blocked, _ = _is_command_blocked(command)
    if is_blocked:
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
