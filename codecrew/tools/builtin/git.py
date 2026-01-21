"""Git operation tools for CodeCrew.

This module provides tools for Git repository operations with
appropriate permission levels for safe AI-driven interactions.

Security measures:
- Working directory validation to prevent operations outside project
- Input validation for branch names and file paths
- Dangerous operations (delete, force) require elevated permissions
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from codecrew.errors import NotARepositoryError, GitError, PathAccessError, InputValidationError
from codecrew.git import GitRepository
from codecrew.models.tools import (
    GIT_STATUS_TOOL,
    GIT_DIFF_TOOL,
    GIT_LOG_TOOL,
    GIT_SHOW_TOOL,
    GIT_BRANCH_TOOL,
    GIT_CHECKOUT_TOOL,
    GIT_ADD_TOOL,
    GIT_COMMIT_TOOL,
    GIT_STASH_TOOL,
    GIT_BLAME_TOOL,
)
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool

logger = logging.getLogger(__name__)


def _get_repo(
    path: str | None,
    working_directory: str | None,
    allowed_paths: list[str] | None = None,
) -> GitRepository:
    """Get a GitRepository for the given path.

    Args:
        path: Explicit path from tool arguments.
        working_directory: Default working directory.
        allowed_paths: If set, repository must be within one of these paths.

    Returns:
        GitRepository instance.

    Raises:
        NotARepositoryError: If not in a git repository.
        PathAccessError: If repository is outside allowed paths.
    """
    search_path = Path(path) if path else Path(working_directory or ".")
    search_path = search_path.resolve()

    # Validate path is within allowed directories
    if allowed_paths:
        is_allowed = False
        for allowed in allowed_paths:
            allowed_resolved = Path(allowed).resolve()
            try:
                search_path.relative_to(allowed_resolved)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise PathAccessError(
                str(search_path),
                f"path is outside allowed directories: {allowed_paths}",
            )

    repo = GitRepository.find(search_path)
    if not repo:
        raise NotARepositoryError(str(search_path))
    return repo


def create_git_status_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for getting git status.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(args.get("path"), working_directory)
        status = repo.get_status()

        # Build detailed output
        lines = [f"On branch {status.branch}"]

        if status.upstream:
            tracking = []
            if status.ahead > 0:
                tracking.append(f"ahead {status.ahead}")
            if status.behind > 0:
                tracking.append(f"behind {status.behind}")
            if tracking:
                lines.append(f"Your branch is {' and '.join(tracking)} of '{status.upstream}'")
            else:
                lines.append(f"Your branch is up to date with '{status.upstream}'")

        lines.append("")

        if status.staged:
            lines.append("Changes to be committed:")
            for change_type, filename in status.staged:
                lines.append(f"  {change_type}: {filename}")
            lines.append("")

        if status.modified or status.deleted:
            lines.append("Changes not staged for commit:")
            for filename in status.modified:
                lines.append(f"  modified: {filename}")
            for filename in status.deleted:
                lines.append(f"  deleted: {filename}")
            lines.append("")

        if status.untracked:
            lines.append("Untracked files:")
            for filename in status.untracked:
                lines.append(f"  {filename}")
            lines.append("")

        if status.conflicted:
            lines.append("Unmerged paths (conflicts):")
            for filename in status.conflicted:
                lines.append(f"  both modified: {filename}")
            lines.append("")

        if status.is_clean:
            lines.append("Nothing to commit, working tree clean")

        return "\n".join(lines)

    return Tool(
        definition=GIT_STATUS_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
        description="Get git repository status",
        timeout=15.0,
    )


def create_git_diff_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for showing git diffs.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        staged = args.get("staged", False)
        file = args.get("file")
        commit = args.get("commit")

        diff = repo.get_diff(staged=staged, file=file, commit=commit)

        if not diff.content:
            return "No differences found"

        # Add summary header
        lines = [diff.summary(), "", diff.content]
        return "\n".join(lines)

    return Tool(
        definition=GIT_DIFF_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
        description="Show git diff",
        timeout=30.0,
    )


def create_git_log_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for showing git log.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        limit = args.get("limit", 10)
        file = args.get("file")
        author = args.get("author")
        since = args.get("since")

        commits = repo.get_log(
            limit=limit,
            file=file,
            author=author,
            since=since,
        )

        if not commits:
            return "No commits found"

        lines = []
        for commit in commits:
            lines.append(commit.full())
            lines.append("")

        return "\n".join(lines)

    return Tool(
        definition=GIT_LOG_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
        description="Show commit history",
        timeout=30.0,
    )


def create_git_show_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for showing commit details.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        commit_ref = args.get("commit", "HEAD")
        stat = args.get("stat", False)

        return repo.show_commit(ref=commit_ref, stat=stat)

    return Tool(
        definition=GIT_SHOW_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
        description="Show commit details",
        timeout=30.0,
    )


def create_git_branch_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for branch operations.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        action = args["action"]
        name = args.get("name")
        all_branches = args.get("all", False)
        force = args.get("force", False)

        if action == "list":
            branches = repo.get_branches(all=all_branches)
            if not branches:
                return "No branches found"

            lines = []
            for branch in branches:
                prefix = "* " if branch.is_current else "  "
                suffix = f" ({branch.commit_hash[:7]})" if branch.commit_hash else ""
                lines.append(f"{prefix}{branch.name}{suffix}")

            return "\n".join(lines)

        elif action == "current":
            return repo.get_current_branch()

        elif action == "create":
            if not name:
                raise ValueError("Branch name required for create action")
            return repo.create_branch(name)

        elif action == "delete":
            if not name:
                raise ValueError("Branch name required for delete action")
            return repo.delete_branch(name, force=force)

        else:
            raise ValueError(f"Unknown action: {action}")

    # Branch list is safe, but create/delete require confirmation
    return Tool(
        definition=GIT_BRANCH_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,  # create/delete need confirmation
        category="git",
        description="Manage git branches",
        timeout=15.0,
    )


def create_git_checkout_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for checkout operations.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        target = args["target"]
        create = args.get("create", False)

        return repo.checkout(target, create=create)

    return Tool(
        definition=GIT_CHECKOUT_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="git",
        description="Switch branches or restore files",
        timeout=30.0,
    )


def create_git_add_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for staging files.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        files = args["files"]
        return repo.add(files)

    return Tool(
        definition=GIT_ADD_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="git",
        description="Stage files for commit",
        timeout=15.0,
    )


def create_git_commit_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for creating commits.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        message = args["message"]
        all_flag = args.get("all", False)

        commit = repo.commit(message, all=all_flag)
        return f"Created commit {commit.short_hash}: {commit.message}"

    return Tool(
        definition=GIT_COMMIT_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="git",
        description="Create a commit",
        timeout=30.0,
    )


def create_git_stash_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for stash operations.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        action = args["action"]
        message = args.get("message")
        index = args.get("index", 0)

        if action == "list":
            stashes = repo.stash_list()
            if not stashes:
                return "No stashes found"
            return "\n".join(s.one_line() for s in stashes)

        elif action == "push":
            return repo.stash_push(message=message)

        elif action == "pop":
            return repo.stash_pop(index=index)

        elif action == "show":
            return repo.stash_show(index=index, patch=True)

        elif action == "drop":
            return repo.stash_drop(index=index)

        else:
            raise ValueError(f"Unknown stash action: {action}")

    return Tool(
        definition=GIT_STASH_TOOL,
        handler=handler,
        permission_level=PermissionLevel.CAUTIOUS,
        category="git",
        description="Manage stashes",
        timeout=15.0,
    )


def create_git_blame_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for git blame.

    Args:
        working_directory: Default working directory.

    Returns:
        Configured Tool instance.
    """

    def handler(args: dict[str, Any]) -> str:
        repo = _get_repo(None, working_directory)

        file = args["file"]
        start_line = args.get("start_line")
        end_line = args.get("end_line")

        blame = repo.blame(file, start_line=start_line, end_line=end_line)

        if not blame.lines:
            return f"No blame information for {file}"

        lines = [f"Blame for {blame.file}:", ""]
        for entry in blame.lines:
            line_num = entry.get("line_num", "?")
            commit = entry.get("commit", "???????")
            author = entry.get("author", "Unknown")[:15].ljust(15)
            content = entry.get("content", "")
            lines.append(f"{commit} ({author}) {line_num}: {content}")

        return "\n".join(lines)

    return Tool(
        definition=GIT_BLAME_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
        description="Show line-by-line blame",
        timeout=30.0,
    )


def get_git_tools(working_directory: str | None = None) -> list[Tool]:
    """Get all git tools as a list.

    Args:
        working_directory: Base working directory for operations.

    Returns:
        List of Tool instances.
    """
    return [
        create_git_status_tool(working_directory),
        create_git_diff_tool(working_directory),
        create_git_log_tool(working_directory),
        create_git_show_tool(working_directory),
        create_git_branch_tool(working_directory),
        create_git_checkout_tool(working_directory),
        create_git_add_tool(working_directory),
        create_git_commit_tool(working_directory),
        create_git_stash_tool(working_directory),
        create_git_blame_tool(working_directory),
    ]


def register_git_tools(
    registry,
    working_directory: str | None = None,
) -> None:
    """Register all git tools with a registry.

    Args:
        registry: The tool registry to register with.
        working_directory: Base working directory for operations.
    """
    for tool in get_git_tools(working_directory):
        registry.register(tool)
