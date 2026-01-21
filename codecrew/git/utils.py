"""Git utility functions for CodeCrew."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Raised when a git command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


def find_git_root(start_path: Path | str) -> Optional[Path]:
    """Find the root of a git repository.

    Walks up the directory tree from start_path looking for a .git directory.

    Args:
        start_path: Path to start searching from.

    Returns:
        Path to the repository root, or None if not in a git repository.
    """
    path = Path(start_path).resolve()

    # Check current path and parents
    for parent in [path] + list(path.parents):
        git_dir = parent / ".git"
        if git_dir.exists():
            return parent

    return None


def is_git_repository(path: Path | str) -> bool:
    """Check if a path is inside a git repository.

    Args:
        path: Path to check.

    Returns:
        True if path is inside a git repository.
    """
    return find_git_root(path) is not None


def run_git_command(
    args: list[str],
    cwd: Path | str | None = None,
    timeout: float = 30.0,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a git command and return the result.

    Args:
        args: Git command arguments (without 'git' prefix).
        cwd: Working directory for the command.
        timeout: Command timeout in seconds.
        check: If True, raise GitError on non-zero exit.

    Returns:
        CompletedProcess with stdout/stderr.

    Raises:
        GitError: If check=True and command fails.
        TimeoutError: If command times out.
    """
    cmd = ["git"] + args

    logger.debug(f"Running git command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if check and result.returncode != 0:
            error_msg = result.stderr.strip() or f"Git command failed with exit code {result.returncode}"
            raise GitError(error_msg, result.returncode, result.stderr)

        return result

    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Git command timed out after {timeout}s: {' '.join(cmd)}")


def parse_git_status(porcelain_output: str) -> dict:
    """Parse git status --porcelain=v1 output.

    Args:
        porcelain_output: Output from 'git status --porcelain=v1'.

    Returns:
        Dictionary with categorized file lists.
    """
    staged = []
    modified = []
    untracked = []
    deleted = []
    renamed = []
    conflicted = []

    for line in porcelain_output.rstrip("\n").split("\n"):
        if not line:
            continue

        # Porcelain format: XY filename
        # X = staged status, Y = working tree status
        if len(line) < 3:
            continue

        x, y = line[0], line[1]
        filename = line[3:]

        # Handle renames (format: R  old -> new)
        if " -> " in filename:
            old_name, new_name = filename.split(" -> ")
            filename = new_name

        # Staged changes (X column)
        if x == "A":
            staged.append(("added", filename))
        elif x == "M":
            staged.append(("modified", filename))
        elif x == "D":
            staged.append(("deleted", filename))
        elif x == "R":
            staged.append(("renamed", filename))
        elif x == "C":
            staged.append(("copied", filename))

        # Working tree changes (Y column)
        if y == "M":
            modified.append(filename)
        elif y == "D":
            deleted.append(filename)
        elif y == "?":
            untracked.append(filename)

        # Conflicts
        if x == "U" or y == "U" or (x == "A" and y == "A") or (x == "D" and y == "D"):
            conflicted.append(filename)

    return {
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
        "deleted": deleted,
        "conflicted": conflicted,
    }


def parse_commit_line(line: str, sep: str = "|") -> dict:
    """Parse a formatted git log line.

    Args:
        line: Line from git log with custom format.
        sep: Separator used in format string.

    Returns:
        Dictionary with commit information.
    """
    parts = line.strip().split(sep)
    if len(parts) >= 5:
        return {
            "hash": parts[0],
            "short_hash": parts[0][:7],
            "author": parts[1],
            "email": parts[2],
            "date": parts[3],
            "message": parts[4],
        }
    return {}


def format_diff_stat(diff_output: str) -> dict:
    """Extract statistics from diff output.

    Args:
        diff_output: Output from git diff --stat.

    Returns:
        Dictionary with diff statistics.
    """
    insertions = 0
    deletions = 0
    files_changed = []

    for line in diff_output.strip().split("\n"):
        # Lines like: "file.py | 10 ++---"
        if "|" in line and "changed" not in line:
            parts = line.split("|")
            if len(parts) >= 2:
                filename = parts[0].strip()
                if filename:
                    files_changed.append(filename)

        # Summary line: "2 files changed, 10 insertions(+), 5 deletions(-)"
        if "changed" in line:
            if "insertion" in line:
                try:
                    ins_part = line.split("insertion")[0].split(",")[-1].strip()
                    insertions = int(ins_part.split()[0])
                except (ValueError, IndexError):
                    pass
            if "deletion" in line:
                try:
                    del_part = line.split("deletion")[0].split(",")[-1].strip()
                    deletions = int(del_part.split()[0])
                except (ValueError, IndexError):
                    pass

    return {
        "files": files_changed,
        "insertions": insertions,
        "deletions": deletions,
    }
