"""File operation tools for CodeCrew.

These tools provide safe file system access with path validation
and appropriate permission levels.

Security measures:
- Path containment validation using Path.relative_to()
- Symlink resolution to prevent traversal attacks
- Explicit blocklist for sensitive system paths
- File size limits to prevent memory exhaustion
"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any

from codecrew.errors import PathAccessError, InputValidationError
from codecrew.models.tools import (
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
    EDIT_FILE_TOOL,
    LIST_DIRECTORY_TOOL,
    SEARCH_FILES_TOOL,
)
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool

logger = logging.getLogger(__name__)

# Sensitive paths that should never be accessed
BLOCKED_PATHS = {
    # Unix/Linux sensitive paths
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/root/.ssh",
    "/root/.bashrc",
    "/root/.bash_history",
    # Windows sensitive paths
    "C:\\Windows\\System32\\config\\SAM",
    "C:\\Windows\\System32\\config\\SYSTEM",
    "C:\\Windows\\System32\\config\\SECURITY",
    # Common secret locations
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.yaml",
    "secrets.yml",
}


def _resolve_path(
    path: str,
    working_directory: str | None = None,
) -> Path:
    """Resolve a path relative to working directory.

    Args:
        path: The path to resolve.
        working_directory: Base directory for relative paths.

    Returns:
        Resolved absolute Path.
    """
    p = Path(path)
    if not p.is_absolute():
        base = Path(working_directory) if working_directory else Path.cwd()
        p = base / p
    return p.resolve()


def _is_path_blocked(path: Path) -> bool:
    """Check if a path is in the blocked list.

    Args:
        path: The resolved path to check.

    Returns:
        True if the path should be blocked.
    """
    # Use forward slashes for consistent matching across platforms
    path_str = str(path).replace("\\", "/")
    path_name = path.name

    # Check exact matches and name-based matches
    for blocked in BLOCKED_PATHS:
        blocked_normalized = blocked.replace("\\", "/")
        if blocked_normalized in path_str or path_name == blocked:
            return True

    return False


def _check_path_allowed(
    path: Path,
    allowed_paths: list[str] | None,
) -> None:
    """Check if a path is within allowed paths.

    Uses Path.relative_to() for proper path containment checking,
    which is resistant to path traversal attacks.

    Args:
        path: The resolved path to check.
        allowed_paths: List of allowed base paths.

    Raises:
        PathAccessError: If path is not within allowed paths or is blocked.
    """
    # First check blocklist
    if _is_path_blocked(path):
        logger.warning(f"Blocked path access attempt: {path}")
        raise PathAccessError(str(path), "access to this path is blocked for security")

    if allowed_paths is None:
        return  # No restrictions

    # Use Path.relative_to() for secure containment check
    # This properly handles symlinks, "..", and other traversal attempts
    for allowed in allowed_paths:
        allowed_resolved = Path(allowed).resolve()
        try:
            # relative_to() raises ValueError if path is not within allowed_resolved
            path.relative_to(allowed_resolved)
            return  # Path is within this allowed directory
        except ValueError:
            continue  # Try next allowed path

    raise PathAccessError(
        str(path),
        f"path is outside allowed directories: {allowed_paths}",
    )


def create_read_file_tool(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    max_file_size: int = 1024 * 1024,  # 1MB default
) -> Tool:
    """Create a tool for reading file contents.

    Args:
        working_directory: Base directory for relative paths.
        allowed_paths: Allowed base paths (None = no restrictions).
        max_file_size: Maximum file size to read in bytes.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        path_str = args["path"]
        path = _resolve_path(path_str, working_directory)
        _check_path_allowed(path, allowed_paths)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # Check file size
        size = path.stat().st_size
        if size > max_file_size:
            raise ValueError(
                f"File too large ({size} bytes). Maximum: {max_file_size} bytes"
            )

        # Try to detect encoding
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try latin-1 as fallback (handles any byte sequence)
            content = path.read_text(encoding="latin-1")

        logger.debug(f"Read file: {path} ({len(content)} chars)")
        return content

    return Tool(
        definition=READ_FILE_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="file",
        description="Read the contents of a file",
        timeout=10.0,
        parallel_safe=True,  # Read-only operation, safe to run concurrently
    )


def create_write_file_tool(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    create_directories: bool = True,
) -> Tool:
    """Create a tool for writing file contents.

    Args:
        working_directory: Base directory for relative paths.
        allowed_paths: Allowed base paths (None = no restrictions).
        create_directories: If True, create parent directories as needed.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        path_str = args["path"]
        content = args["content"]

        path = _resolve_path(path_str, working_directory)
        _check_path_allowed(path, allowed_paths)

        # Create parent directories if needed
        if create_directories and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directories: {path.parent}")

        # Check if file exists (for logging)
        existed = path.exists()

        path.write_text(content, encoding="utf-8")

        action = "Updated" if existed else "Created"
        logger.info(f"{action} file: {path} ({len(content)} chars)")

        return f"Successfully wrote {len(content)} characters to {path}"

    return Tool(
        definition=WRITE_FILE_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="file",
        description="Write content to a file (creates or overwrites)",
        timeout=10.0,
    )


def create_edit_file_tool(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
) -> Tool:
    """Create a tool for making targeted edits to files.

    Args:
        working_directory: Base directory for relative paths.
        allowed_paths: Allowed base paths (None = no restrictions).

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        path_str = args["path"]
        edits = args["edits"]

        path = _resolve_path(path_str, working_directory)
        _check_path_allowed(path, allowed_paths)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_text(encoding="utf-8")
        original_content = content

        # Apply edits
        changes_made = 0
        for edit in edits:
            old_text = edit["old_text"]
            new_text = edit["new_text"]

            if old_text not in content:
                raise ValueError(
                    f"Text not found in file: {old_text[:50]}..."
                    if len(old_text) > 50
                    else f"Text not found in file: {old_text}"
                )

            content = content.replace(old_text, new_text, 1)
            changes_made += 1

        # Only write if changes were made
        if content != original_content:
            path.write_text(content, encoding="utf-8")
            logger.info(f"Edited file: {path} ({changes_made} changes)")
            return f"Successfully made {changes_made} edit(s) to {path}"

        return "No changes were necessary"

    return Tool(
        definition=EDIT_FILE_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="file",
        description="Make targeted text replacements in a file",
        timeout=10.0,
    )


def create_list_directory_tool(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    max_entries: int = 1000,
) -> Tool:
    """Create a tool for listing directory contents.

    Args:
        working_directory: Base directory for relative paths.
        allowed_paths: Allowed base paths (None = no restrictions).
        max_entries: Maximum number of entries to return.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        path_str = args["path"]
        recursive = args.get("recursive", False)

        path = _resolve_path(path_str, working_directory)
        _check_path_allowed(path, allowed_paths)

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        entries = []
        count = 0

        if recursive:
            for item in path.rglob("*"):
                if count >= max_entries:
                    break
                try:
                    rel_path = item.relative_to(path)
                    entry_type = "dir" if item.is_dir() else "file"
                    size = item.stat().st_size if item.is_file() else 0
                    entries.append(f"{entry_type}: {rel_path} ({size} bytes)")
                    count += 1
                except (PermissionError, OSError):
                    continue
        else:
            for item in path.iterdir():
                if count >= max_entries:
                    break
                try:
                    entry_type = "dir" if item.is_dir() else "file"
                    size = item.stat().st_size if item.is_file() else 0
                    entries.append(f"{entry_type}: {item.name} ({size} bytes)")
                    count += 1
                except (PermissionError, OSError):
                    continue

        result = f"Contents of {path}:\n"
        result += "\n".join(sorted(entries))

        if count >= max_entries:
            result += f"\n... (truncated at {max_entries} entries)"

        logger.debug(f"Listed directory: {path} ({count} entries)")
        return result

    return Tool(
        definition=LIST_DIRECTORY_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="file",
        description="List files and directories",
        timeout=30.0,
        parallel_safe=True,  # Read-only operation, safe to run concurrently
    )


def create_search_files_tool(
    working_directory: str | None = None,
    allowed_paths: list[str] | None = None,
    max_results: int = 100,
    max_context_lines: int = 3,
) -> Tool:
    """Create a tool for searching file contents.

    Args:
        working_directory: Base directory for relative paths.
        allowed_paths: Allowed base paths (None = no restrictions).
        max_results: Maximum number of matches to return.
        max_context_lines: Lines of context around matches.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        pattern = args["pattern"]
        path_str = args.get("path", ".")
        file_pattern = args.get("file_pattern", "*")

        path = _resolve_path(path_str, working_directory)
        _check_path_allowed(path, allowed_paths)

        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Compile regex
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        results = []
        files_searched = 0

        # Get files to search
        if path.is_file():
            files = [path]
        else:
            files = [
                f
                for f in path.rglob("*")
                if f.is_file() and fnmatch.fnmatch(f.name, file_pattern)
            ]

        for file_path in files:
            if len(results) >= max_results:
                break

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                files_searched += 1

                for i, line in enumerate(lines):
                    if len(results) >= max_results:
                        break

                    if regex.search(line):
                        # Get context
                        start = max(0, i - max_context_lines)
                        end = min(len(lines), i + max_context_lines + 1)

                        context_lines = []
                        for j in range(start, end):
                            prefix = ">" if j == i else " "
                            context_lines.append(f"{prefix} {j + 1}: {lines[j]}")

                        rel_path = (
                            file_path.relative_to(path)
                            if path.is_dir()
                            else file_path.name
                        )
                        results.append(
                            f"\n{rel_path}:\n" + "\n".join(context_lines)
                        )

            except (PermissionError, OSError, UnicodeDecodeError):
                continue

        if not results:
            return f"No matches found for '{pattern}' in {files_searched} files"

        output = f"Found {len(results)} match(es) for '{pattern}':\n"
        output += "\n".join(results)

        if len(results) >= max_results:
            output += f"\n\n... (limited to {max_results} results)"

        logger.debug(
            f"Search complete: {len(results)} matches in {files_searched} files"
        )
        return output

    return Tool(
        definition=SEARCH_FILES_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="file",
        description="Search for patterns in file contents",
        timeout=60.0,
        parallel_safe=True,  # Read-only operation, safe to run concurrently
    )
