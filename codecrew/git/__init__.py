"""Git integration for CodeCrew.

This package provides Git repository detection, status viewing,
and safe Git operations for AI models.
"""

from codecrew.git.repository import (
    GitRepository,
    GitStatus,
    GitCommit,
    GitDiff,
    GitBranch,
    GitStash,
    GitBlame,
    GitError,
)
from codecrew.git.utils import (
    find_git_root,
    is_git_repository,
    run_git_command,
    parse_git_status,
)

__all__ = [
    # Main class
    "GitRepository",
    # Data classes
    "GitStatus",
    "GitCommit",
    "GitDiff",
    "GitBranch",
    "GitStash",
    "GitBlame",
    "GitError",
    # Utility functions
    "find_git_root",
    "is_git_repository",
    "run_git_command",
    "parse_git_status",
]
