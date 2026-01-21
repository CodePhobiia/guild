"""Git repository operations for CodeCrew."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from codecrew.git.utils import (
    GitError,
    find_git_root,
    run_git_command,
    parse_git_status,
    parse_commit_line,
    format_diff_stat,
)

logger = logging.getLogger(__name__)

# Re-export GitError
__all__ = [
    "GitRepository",
    "GitStatus",
    "GitCommit",
    "GitDiff",
    "GitBranch",
    "GitStash",
    "GitBlame",
    "GitError",
]


@dataclass
class GitStatus:
    """Represents the current git repository status."""

    branch: str
    is_clean: bool
    staged: list[tuple[str, str]] = field(default_factory=list)  # (status, filename)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    upstream: Optional[str] = None

    def summary(self) -> str:
        """Get a summary string of the status."""
        parts = [f"On branch {self.branch}"]

        if self.upstream:
            if self.ahead > 0 or self.behind > 0:
                tracking = []
                if self.ahead > 0:
                    tracking.append(f"ahead {self.ahead}")
                if self.behind > 0:
                    tracking.append(f"behind {self.behind}")
                parts.append(f"Your branch is {' and '.join(tracking)} of '{self.upstream}'")

        if self.is_clean:
            parts.append("Nothing to commit, working tree clean")
        else:
            if self.staged:
                parts.append(f"Staged: {len(self.staged)} file(s)")
            if self.modified:
                parts.append(f"Modified: {len(self.modified)} file(s)")
            if self.deleted:
                parts.append(f"Deleted: {len(self.deleted)} file(s)")
            if self.untracked:
                parts.append(f"Untracked: {len(self.untracked)} file(s)")
            if self.conflicted:
                parts.append(f"Conflicts: {len(self.conflicted)} file(s)")

        return "\n".join(parts)


@dataclass
class GitCommit:
    """Represents a git commit."""

    hash: str
    short_hash: str
    author: str
    email: str
    date: str
    message: str

    def one_line(self) -> str:
        """Get a one-line representation."""
        return f"{self.short_hash} {self.message[:60]}{'...' if len(self.message) > 60 else ''}"

    def full(self) -> str:
        """Get full commit details."""
        return f"""commit {self.hash}
Author: {self.author} <{self.email}>
Date:   {self.date}

    {self.message}"""


@dataclass
class GitDiff:
    """Represents a git diff."""

    files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    content: str = ""

    def summary(self) -> str:
        """Get a summary string."""
        if not self.files:
            return "No changes"
        return f"{len(self.files)} file(s) changed, {self.insertions} insertions(+), {self.deletions} deletions(-)"


@dataclass
class GitBranch:
    """Represents a git branch."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    tracking: Optional[str] = None
    commit_hash: Optional[str] = None


@dataclass
class GitStash:
    """Represents a git stash entry."""

    index: int
    branch: str
    message: str
    hash: Optional[str] = None

    def one_line(self) -> str:
        """Get a one-line representation."""
        return f"stash@{{{self.index}}}: On {self.branch}: {self.message}"


@dataclass
class GitBlame:
    """Represents git blame output for a file."""

    file: str
    lines: list[dict] = field(default_factory=list)  # Each line: {commit, author, date, line_num, content}


class GitRepository:
    """Represents a Git repository with operations."""

    def __init__(self, path: Path | str):
        """Initialize a GitRepository.

        Args:
            path: Path to the repository root.
        """
        self.path = Path(path).resolve()
        self._git_dir = self.path / ".git"

        if not self._git_dir.exists():
            raise GitError(f"Not a git repository: {self.path}")

    @classmethod
    def find(cls, start_path: Path | str) -> Optional["GitRepository"]:
        """Find a git repository from a starting path.

        Args:
            start_path: Path to start searching from.

        Returns:
            GitRepository instance, or None if not found.
        """
        root = find_git_root(start_path)
        if root:
            return cls(root)
        return None

    @classmethod
    def is_git_repo(cls, path: Path | str) -> bool:
        """Check if a path is inside a git repository.

        Args:
            path: Path to check.

        Returns:
            True if path is in a git repository.
        """
        return find_git_root(path) is not None

    def _run(self, args: list[str], **kwargs) -> str:
        """Run a git command in this repository.

        Args:
            args: Git command arguments.
            **kwargs: Additional arguments to run_git_command.

        Returns:
            Command stdout.
        """
        result = run_git_command(args, cwd=self.path, **kwargs)
        return result.stdout.strip()

    def get_status(self) -> GitStatus:
        """Get the current repository status.

        Returns:
            GitStatus with current state.
        """
        # Get branch info
        branch_output = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_output if branch_output != "HEAD" else "(detached)"

        # Get upstream tracking info
        upstream = None
        ahead = 0
        behind = 0
        try:
            upstream = self._run(["rev-parse", "--abbrev-ref", "@{upstream}"])
            # Get ahead/behind counts
            counts = self._run(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
            parts = counts.split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])
        except GitError:
            pass  # No upstream configured

        # Get porcelain status
        status_output = self._run(["status", "--porcelain=v1"])
        parsed = parse_git_status(status_output)

        is_clean = not any([
            parsed["staged"],
            parsed["modified"],
            parsed["untracked"],
            parsed["deleted"],
            parsed["conflicted"],
        ])

        return GitStatus(
            branch=branch,
            is_clean=is_clean,
            staged=parsed["staged"],
            modified=parsed["modified"],
            untracked=parsed["untracked"],
            deleted=parsed["deleted"],
            conflicted=parsed["conflicted"],
            ahead=ahead,
            behind=behind,
            upstream=upstream,
        )

    def get_diff(
        self,
        staged: bool = False,
        file: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> GitDiff:
        """Get diff of changes.

        Args:
            staged: If True, show staged changes.
            file: Specific file to diff.
            commit: Compare with specific commit.

        Returns:
            GitDiff with changes.
        """
        args = ["diff"]

        if staged:
            args.append("--cached")

        if commit:
            args.append(commit)

        if file:
            args.extend(["--", file])

        # Get full diff
        content = self._run(args)

        # Get stat summary
        stat_args = args + ["--stat"]
        stat_output = self._run(stat_args)
        stats = format_diff_stat(stat_output)

        return GitDiff(
            files=stats["files"],
            insertions=stats["insertions"],
            deletions=stats["deletions"],
            content=content,
        )

    def get_log(
        self,
        limit: int = 10,
        file: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> list[GitCommit]:
        """Get commit history.

        Args:
            limit: Maximum number of commits.
            file: Filter by file.
            author: Filter by author.
            since: Show commits since date.
            until: Show commits until date.

        Returns:
            List of GitCommit objects.
        """
        # Use a custom format with separator
        fmt = "%H|%an|%ae|%ai|%s"
        args = ["log", f"--format={fmt}", f"-n{limit}"]

        if author:
            args.append(f"--author={author}")
        if since:
            args.append(f"--since={since}")
        if until:
            args.append(f"--until={until}")
        if file:
            args.extend(["--", file])

        output = self._run(args)

        commits = []
        for line in output.split("\n"):
            if line:
                parsed = parse_commit_line(line)
                if parsed:
                    commits.append(GitCommit(**parsed))

        return commits

    def get_commit(self, ref: str = "HEAD") -> GitCommit:
        """Get details of a specific commit.

        Args:
            ref: Commit reference (hash, branch, tag, etc.).

        Returns:
            GitCommit object.
        """
        fmt = "%H|%an|%ae|%ai|%s"
        output = self._run(["show", "-s", f"--format={fmt}", ref])
        parsed = parse_commit_line(output)
        if not parsed:
            raise GitError(f"Could not parse commit: {ref}")
        return GitCommit(**parsed)

    def show_commit(self, ref: str = "HEAD", stat: bool = False) -> str:
        """Show a commit with diff.

        Args:
            ref: Commit reference.
            stat: If True, show diffstat only.

        Returns:
            Commit details as string.
        """
        args = ["show", ref]
        if stat:
            args.append("--stat")
        return self._run(args)

    def get_branches(self, remote: bool = False, all: bool = False) -> list[GitBranch]:
        """Get list of branches.

        Args:
            remote: Show only remote branches.
            all: Show all branches (local and remote).

        Returns:
            List of GitBranch objects.
        """
        args = ["branch"]
        if all:
            args.append("-a")
        elif remote:
            args.append("-r")

        # Add verbose for tracking info
        args.append("-v")

        output = self._run(args)

        branches = []
        for line in output.split("\n"):
            if not line.strip():
                continue

            is_current = line.startswith("*")
            line = line.lstrip("* ").strip()

            # Parse line: "branch_name hash message" or "branch_name -> origin/main"
            parts = line.split()
            if not parts:
                continue

            name = parts[0]
            is_remote_branch = name.startswith("remotes/") or "/" in name

            # Get commit hash if present
            commit_hash = None
            if len(parts) > 1 and not parts[1].startswith("->"):
                commit_hash = parts[1]

            branches.append(GitBranch(
                name=name,
                is_current=is_current,
                is_remote=is_remote_branch,
                commit_hash=commit_hash,
            ))

        return branches

    def get_current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Branch name or '(detached)' if in detached HEAD state.
        """
        output = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return output if output != "HEAD" else "(detached)"

    def get_remotes(self) -> dict[str, str]:
        """Get remote repositories.

        Returns:
            Dictionary of remote names to URLs.
        """
        output = self._run(["remote", "-v"])
        remotes = {}

        for line in output.split("\n"):
            if line and "(fetch)" in line:
                parts = line.split()
                if len(parts) >= 2:
                    remotes[parts[0]] = parts[1]

        return remotes

    def add(self, files: list[str]) -> str:
        """Stage files for commit.

        Args:
            files: List of files to add (use ['.'] for all).

        Returns:
            Status message.
        """
        args = ["add"] + files
        self._run(args)
        return f"Staged {len(files)} file(s)"

    def commit(self, message: str, all: bool = False) -> GitCommit:
        """Create a commit.

        Args:
            message: Commit message.
            all: If True, auto-stage modified/deleted files.

        Returns:
            The created commit.
        """
        args = ["commit", "-m", message]
        if all:
            args.insert(1, "-a")

        self._run(args)

        # Return the created commit
        return self.get_commit("HEAD")

    def checkout(self, target: str, create: bool = False) -> str:
        """Switch branches or restore files.

        Args:
            target: Branch name or commit.
            create: If True, create branch if it doesn't exist.

        Returns:
            Status message.
        """
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(target)

        output = self._run(args)
        return output or f"Switched to {'new branch' if create else ''} '{target}'"

    def create_branch(self, name: str, start_point: Optional[str] = None) -> str:
        """Create a new branch.

        Args:
            name: Branch name.
            start_point: Starting commit (default: HEAD).

        Returns:
            Status message.
        """
        args = ["branch", name]
        if start_point:
            args.append(start_point)

        self._run(args)
        return f"Created branch '{name}'"

    def delete_branch(self, name: str, force: bool = False) -> str:
        """Delete a branch.

        Args:
            name: Branch name.
            force: Force delete even if not merged.

        Returns:
            Status message.
        """
        args = ["branch", "-d" if not force else "-D", name]
        self._run(args)
        return f"Deleted branch '{name}'"

    def stash_list(self) -> list[GitStash]:
        """List all stashes.

        Returns:
            List of GitStash objects.
        """
        try:
            output = self._run(["stash", "list"])
        except GitError:
            return []

        stashes = []
        for line in output.split("\n"):
            if not line:
                continue

            # Format: stash@{0}: On branch: message
            match = re.match(r"stash@\{(\d+)\}: On (\w+): (.+)", line)
            if match:
                stashes.append(GitStash(
                    index=int(match.group(1)),
                    branch=match.group(2),
                    message=match.group(3),
                ))
            else:
                # Alternative format: stash@{0}: WIP on branch: hash message
                match = re.match(r"stash@\{(\d+)\}: WIP on (\w+): (.+)", line)
                if match:
                    stashes.append(GitStash(
                        index=int(match.group(1)),
                        branch=match.group(2),
                        message=match.group(3),
                    ))

        return stashes

    def stash_push(self, message: Optional[str] = None) -> str:
        """Stash current changes.

        Args:
            message: Optional stash message.

        Returns:
            Status message.
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        output = self._run(args)
        return output or "Stashed changes"

    def stash_pop(self, index: int = 0) -> str:
        """Pop a stash.

        Args:
            index: Stash index to pop.

        Returns:
            Status message.
        """
        args = ["stash", "pop", f"stash@{{{index}}}"]
        output = self._run(args)
        return output or f"Applied and dropped stash@{{{index}}}"

    def stash_show(self, index: int = 0, patch: bool = False) -> str:
        """Show stash contents.

        Args:
            index: Stash index.
            patch: If True, show patch diff.

        Returns:
            Stash contents.
        """
        args = ["stash", "show"]
        if patch:
            args.append("-p")
        args.append(f"stash@{{{index}}}")

        return self._run(args)

    def stash_drop(self, index: int = 0) -> str:
        """Drop a stash.

        Args:
            index: Stash index to drop.

        Returns:
            Status message.
        """
        args = ["stash", "drop", f"stash@{{{index}}}"]
        output = self._run(args)
        return output or f"Dropped stash@{{{index}}}"

    def blame(
        self,
        file: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> GitBlame:
        """Get blame information for a file.

        Args:
            file: File to blame.
            start_line: Starting line number.
            end_line: Ending line number.

        Returns:
            GitBlame with line-by-line information.
        """
        args = ["blame", "--line-porcelain"]

        if start_line is not None:
            if end_line is not None:
                args.extend(["-L", f"{start_line},{end_line}"])
            else:
                args.extend(["-L", f"{start_line},"])

        args.append(file)
        output = self._run(args)

        lines = []
        current = {}

        for line in output.split("\n"):
            if not line:
                continue

            # First line of each block: hash orig_line final_line [group_lines]
            if re.match(r"^[0-9a-f]{40}", line):
                parts = line.split()
                current = {
                    "commit": parts[0][:7],
                    "line_num": int(parts[2]) if len(parts) > 2 else 0,
                }
            elif line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("author-time "):
                current["date"] = line[12:]
            elif line.startswith("\t"):
                current["content"] = line[1:]
                lines.append(current.copy())
                current = {}

        return GitBlame(file=file, lines=lines)
