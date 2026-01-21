# Phase 8: Git Integration

## Overview
Phase 8 adds comprehensive Git integration to CodeCrew, enabling AI models to understand, navigate, and work with Git repositories. This includes repository detection, status viewing, history browsing, and safe commit operations.

## Goals
1. Automatic Git repository detection
2. Git status and diff viewing tools
3. Commit and branch management
4. Git history and log viewing
5. Stash operations
6. Git-related slash commands
7. Safe operations with appropriate permission levels

## Architecture

### New Files

```
codecrew/tools/builtin/
└── git.py               # Git operation tools

codecrew/git/
├── __init__.py          # Package exports
├── repository.py        # GitRepository class for repo operations
└── utils.py             # Git utility functions

tests/test_tools/
└── test_git.py          # Git tools tests

tests/test_git/
├── __init__.py          # Test package
└── test_repository.py   # GitRepository tests
```

### Modified Files
- `codecrew/tools/builtin/__init__.py` - Register git tools
- `codecrew/models/tools.py` - Add git tool definitions
- `codecrew/ui/handlers/commands.py` - Add git slash commands

## Implementation Details

### 1. Git Repository Detection (`git/repository.py`)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess

@dataclass
class GitStatus:
    """Represents the current git status."""
    branch: str
    is_clean: bool
    staged: list[str]
    modified: list[str]
    untracked: list[str]
    ahead: int = 0
    behind: int = 0

@dataclass
class GitCommit:
    """Represents a git commit."""
    hash: str
    short_hash: str
    author: str
    email: str
    date: str
    message: str

@dataclass
class GitDiff:
    """Represents a git diff."""
    files: list[str]
    insertions: int
    deletions: int
    content: str

class GitRepository:
    """Represents a Git repository with operations."""

    def __init__(self, path: Path):
        self.path = path
        self._git_dir = path / ".git"

    @classmethod
    def find(cls, start_path: Path) -> Optional["GitRepository"]:
        """Find a git repository from a starting path."""

    @classmethod
    def is_git_repo(cls, path: Path) -> bool:
        """Check if a path is inside a git repository."""

    def get_status(self) -> GitStatus:
        """Get the current repository status."""

    def get_diff(self, staged: bool = False, file: str = None) -> GitDiff:
        """Get diff of changes."""

    def get_log(self, limit: int = 10, file: str = None) -> list[GitCommit]:
        """Get commit history."""

    def get_branches(self, remote: bool = False) -> list[str]:
        """Get list of branches."""

    def get_current_branch(self) -> str:
        """Get current branch name."""

    def get_remotes(self) -> dict[str, str]:
        """Get remote repositories."""
```

### 2. Git Tool Definitions (`models/tools.py` additions)

```python
GIT_STATUS_TOOL = ToolDefinition(
    name="git_status",
    description="Get the current git repository status including branch, staged/unstaged changes, and untracked files",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the repository (optional, uses current directory)",
            required=False,
        ),
    ],
)

GIT_DIFF_TOOL = ToolDefinition(
    name="git_diff",
    description="Show changes between commits, commit and working tree, etc.",
    parameters=[
        ToolParameter(
            name="staged",
            type="boolean",
            description="Show staged changes instead of unstaged",
            required=False,
        ),
        ToolParameter(
            name="file",
            type="string",
            description="Specific file to diff",
            required=False,
        ),
        ToolParameter(
            name="commit",
            type="string",
            description="Compare with specific commit (e.g., HEAD~1, abc123)",
            required=False,
        ),
    ],
)

GIT_LOG_TOOL = ToolDefinition(
    name="git_log",
    description="Show commit history",
    parameters=[
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of commits to show (default: 10)",
            required=False,
        ),
        ToolParameter(
            name="file",
            type="string",
            description="Show history for specific file",
            required=False,
        ),
        ToolParameter(
            name="author",
            type="string",
            description="Filter by author",
            required=False,
        ),
        ToolParameter(
            name="since",
            type="string",
            description="Show commits since date (e.g., '2024-01-01', '1 week ago')",
            required=False,
        ),
    ],
)

GIT_SHOW_TOOL = ToolDefinition(
    name="git_show",
    description="Show details of a specific commit",
    parameters=[
        ToolParameter(
            name="commit",
            type="string",
            description="Commit hash or reference (e.g., HEAD, abc123, main~2)",
        ),
        ToolParameter(
            name="stat",
            type="boolean",
            description="Show diffstat instead of full diff",
            required=False,
        ),
    ],
)

GIT_BRANCH_TOOL = ToolDefinition(
    name="git_branch",
    description="List, create, or delete branches",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform",
            enum=["list", "create", "delete", "current"],
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Branch name (for create/delete)",
            required=False,
        ),
        ToolParameter(
            name="remote",
            type="boolean",
            description="Include/operate on remote branches",
            required=False,
        ),
    ],
)

GIT_CHECKOUT_TOOL = ToolDefinition(
    name="git_checkout",
    description="Switch branches or restore working tree files",
    parameters=[
        ToolParameter(
            name="target",
            type="string",
            description="Branch name or commit to checkout",
        ),
        ToolParameter(
            name="create",
            type="boolean",
            description="Create branch if it doesn't exist (-b flag)",
            required=False,
        ),
    ],
)

GIT_COMMIT_TOOL = ToolDefinition(
    name="git_commit",
    description="Record changes to the repository",
    parameters=[
        ToolParameter(
            name="message",
            type="string",
            description="Commit message",
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Automatically stage modified/deleted files (-a flag)",
            required=False,
        ),
    ],
)

GIT_ADD_TOOL = ToolDefinition(
    name="git_add",
    description="Add file contents to the staging area",
    parameters=[
        ToolParameter(
            name="files",
            type="array",
            description="Files to add (use ['.'] for all)",
            items={"type": "string"},
        ),
    ],
)

GIT_STASH_TOOL = ToolDefinition(
    name="git_stash",
    description="Stash changes in working directory",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Stash action",
            enum=["push", "pop", "list", "show", "drop", "clear"],
        ),
        ToolParameter(
            name="message",
            type="string",
            description="Message for stash push",
            required=False,
        ),
        ToolParameter(
            name="index",
            type="integer",
            description="Stash index for pop/show/drop",
            required=False,
        ),
    ],
)

GIT_BLAME_TOOL = ToolDefinition(
    name="git_blame",
    description="Show what revision and author last modified each line of a file",
    parameters=[
        ToolParameter(
            name="file",
            type="string",
            description="File to blame",
        ),
        ToolParameter(
            name="lines",
            type="string",
            description="Line range (e.g., '10,20' for lines 10-20)",
            required=False,
        ),
    ],
)
```

### 3. Git Tools Implementation (`tools/builtin/git.py`)

```python
"""Git operation tools for CodeCrew."""

from codecrew.git import GitRepository
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import Tool

def create_git_status_tool(working_directory: str | None = None) -> Tool:
    """Create a tool for getting git status."""

    def handler(args: dict[str, Any]) -> str:
        repo = GitRepository.find(Path(args.get("path", working_directory or ".")))
        if not repo:
            return "Not a git repository"

        status = repo.get_status()
        # Format and return status
        ...

    return Tool(
        definition=GIT_STATUS_TOOL,
        handler=handler,
        permission_level=PermissionLevel.SAFE,
        category="git",
    )

# Similar implementations for:
# - create_git_diff_tool
# - create_git_log_tool
# - create_git_show_tool
# - create_git_branch_tool (SAFE for list, CAUTIOUS for create/delete)
# - create_git_checkout_tool (CAUTIOUS)
# - create_git_commit_tool (CAUTIOUS)
# - create_git_add_tool (CAUTIOUS)
# - create_git_stash_tool (CAUTIOUS)
# - create_git_blame_tool (SAFE)
```

### 4. Permission Levels

| Tool | Permission Level | Reason |
|------|-----------------|--------|
| git_status | SAFE | Read-only |
| git_diff | SAFE | Read-only |
| git_log | SAFE | Read-only |
| git_show | SAFE | Read-only |
| git_blame | SAFE | Read-only |
| git_branch (list) | SAFE | Read-only |
| git_branch (create/delete) | CAUTIOUS | Modifies repository |
| git_checkout | CAUTIOUS | Changes working tree |
| git_add | CAUTIOUS | Modifies staging area |
| git_commit | CAUTIOUS | Creates commit |
| git_stash | CAUTIOUS | Modifies stash |

### 5. Slash Commands

Add to `commands.py`:

```python
COMMAND_GROUPS = {
    ...
    "Git": ["/git", "/status", "/diff", "/log", "/branch", "/commit"],
}

# /git - Show git status summary
# /status - Detailed git status
# /diff [file] - Show diff
# /log [n] - Show last n commits
# /branch - List branches
# /commit <msg> - Quick commit (if changes staged)
```

## Testing Plan

### Unit Tests (`test_git/test_repository.py`)
1. Test repository detection
2. Test status parsing
3. Test diff parsing
4. Test log parsing
5. Test branch operations

### Tool Tests (`test_tools/test_git.py`)
1. Test git_status tool
2. Test git_diff tool
3. Test git_log tool
4. Test git_show tool
5. Test git_branch tool
6. Test git_checkout tool
7. Test git_commit tool
8. Test git_add tool
9. Test git_stash tool
10. Test git_blame tool

### Integration Tests
- Test git operations in mock repository
- Test permission levels
- Test error handling for non-git directories

## Implementation Order

1. **Phase 8.1**: Core Git Module
   - Create `codecrew/git/repository.py`
   - Create `codecrew/git/utils.py`
   - Write basic tests

2. **Phase 8.2**: Read-Only Tools
   - Add tool definitions
   - Implement git_status, git_diff, git_log, git_show, git_blame
   - Write tests

3. **Phase 8.3**: Modification Tools
   - Implement git_branch, git_checkout, git_add, git_commit, git_stash
   - Write tests

4. **Phase 8.4**: Slash Commands
   - Add git commands to CommandHandler
   - Update help system
   - Write tests

5. **Phase 8.5**: Integration
   - Register tools
   - Full integration testing
   - Documentation

## Success Criteria

- [ ] Git repository auto-detection works
- [ ] git_status shows accurate status
- [ ] git_diff shows correct changes
- [ ] git_log shows commit history
- [ ] git_show displays commit details
- [ ] git_blame shows line history
- [ ] git_branch lists/creates/deletes branches
- [ ] git_checkout switches branches safely
- [ ] git_add stages files correctly
- [ ] git_commit creates commits
- [ ] git_stash manages stashes
- [ ] All slash commands functional
- [ ] Proper permission levels enforced
- [ ] 80+ new tests passing
- [ ] Total tests > 720
