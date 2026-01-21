"""Tests for Git tools."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from codecrew.tools.builtin.git import (
    create_git_status_tool,
    create_git_diff_tool,
    create_git_log_tool,
    create_git_show_tool,
    create_git_branch_tool,
    create_git_checkout_tool,
    create_git_add_tool,
    create_git_commit_tool,
    create_git_stash_tool,
    create_git_blame_tool,
    get_git_tools,
    register_git_tools,
)
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import ToolRegistry
from codecrew.git.repository import GitStatus, GitCommit, GitDiff, GitBranch, GitStash, GitBlame


class TestGitStatusTool:
    """Tests for git_status tool."""

    def test_tool_creation(self):
        """Test tool creation and attributes."""
        tool = create_git_status_tool()

        assert tool.name == "git_status"
        assert tool.permission_level == PermissionLevel.SAFE
        assert tool.category == "git"

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_success(self, mock_repo_class, tmp_path):
        """Test successful status retrieval."""
        mock_repo = MagicMock()
        mock_repo.get_status.return_value = GitStatus(
            branch="main",
            is_clean=False,
            upstream="origin/main",
            ahead=1,
            behind=0,
            staged=[("added", "new.py")],
            modified=["changed.py"],
        )
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_status_tool(working_directory=str(tmp_path))
        result = tool.handler({})

        assert "main" in result
        assert "origin/main" in result
        assert "new.py" in result
        assert "changed.py" in result

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_not_repo(self, mock_repo_class):
        """Test when not in git repository."""
        mock_repo_class.find.return_value = None

        tool = create_git_status_tool()
        with pytest.raises(Exception) as exc_info:
            tool.handler({})

        assert "not a git repository" in str(exc_info.value).lower()


class TestGitDiffTool:
    """Tests for git_diff tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_diff_tool()

        assert tool.name == "git_diff"
        assert tool.permission_level == PermissionLevel.SAFE

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_with_content(self, mock_repo_class):
        """Test diff with changes."""
        mock_repo = MagicMock()
        mock_repo.get_diff.return_value = GitDiff(
            content="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            files=["file.py"],
            insertions=1,
            deletions=1,
        )
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_diff_tool()
        result = tool.handler({})

        assert "old" in result
        assert "new" in result

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_staged_flag(self, mock_repo_class):
        """Test diff with staged flag."""
        mock_repo = MagicMock()
        mock_repo.get_diff.return_value = GitDiff(content="diff content", files=["file.py"])
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_diff_tool()
        tool.handler({"staged": True})

        mock_repo.get_diff.assert_called_with(staged=True, file=None, commit=None)

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_no_changes(self, mock_repo_class):
        """Test diff with no changes."""
        mock_repo = MagicMock()
        mock_repo.get_diff.return_value = GitDiff(content="", files=[])
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_diff_tool()
        result = tool.handler({})

        assert "no differences" in result.lower()


class TestGitLogTool:
    """Tests for git_log tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_log_tool()

        assert tool.name == "git_log"
        assert tool.permission_level == PermissionLevel.SAFE

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_success(self, mock_repo_class):
        """Test successful log retrieval."""
        mock_repo = MagicMock()
        mock_repo.get_log.return_value = [
            GitCommit(hash="abc1234", short_hash="abc1234", message="First commit", author="John", email="john@test.com", date="2024-01-15"),
            GitCommit(hash="def5678", short_hash="def5678", message="Second commit", author="Jane", email="jane@test.com", date="2024-01-16"),
        ]
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_log_tool()
        result = tool.handler({})

        assert "abc1234" in result
        assert "First commit" in result
        assert "John" in result

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_with_limit(self, mock_repo_class):
        """Test log with custom limit."""
        mock_repo = MagicMock()
        mock_repo.get_log.return_value = []
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_log_tool()
        tool.handler({"limit": 5})

        mock_repo.get_log.assert_called_with(limit=5, file=None, author=None, since=None)


class TestGitShowTool:
    """Tests for git_show tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_show_tool()

        assert tool.name == "git_show"
        assert tool.permission_level == PermissionLevel.SAFE

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_success(self, mock_repo_class):
        """Test successful show."""
        mock_repo = MagicMock()
        mock_repo.show_commit.return_value = "commit abc1234\nAuthor: John\n\nInitial commit"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_show_tool()
        result = tool.handler({"commit": "abc1234"})

        assert "Initial commit" in result


class TestGitBranchTool:
    """Tests for git_branch tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_branch_tool()

        assert tool.name == "git_branch"
        assert tool.permission_level == PermissionLevel.CAUTIOUS  # Create/delete need confirmation

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_list(self, mock_repo_class):
        """Test branch list action."""
        mock_repo = MagicMock()
        mock_repo.get_branches.return_value = [
            GitBranch(name="main", is_current=True),
            GitBranch(name="feature", is_current=False),
        ]
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_branch_tool()
        result = tool.handler({"action": "list"})

        assert "main" in result
        assert "feature" in result

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_current(self, mock_repo_class):
        """Test branch current action."""
        mock_repo = MagicMock()
        mock_repo.get_current_branch.return_value = "feature-branch"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_branch_tool()
        result = tool.handler({"action": "current"})

        assert result == "feature-branch"

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_create(self, mock_repo_class):
        """Test branch create action."""
        mock_repo = MagicMock()
        mock_repo.create_branch.return_value = "Created branch 'new-feature'"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_branch_tool()
        result = tool.handler({"action": "create", "name": "new-feature"})

        mock_repo.create_branch.assert_called_with("new-feature")

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_delete(self, mock_repo_class):
        """Test branch delete action."""
        mock_repo = MagicMock()
        mock_repo.delete_branch.return_value = "Deleted branch 'old-feature'"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_branch_tool()
        result = tool.handler({"action": "delete", "name": "old-feature"})

        mock_repo.delete_branch.assert_called_with("old-feature", force=False)

    def test_handler_create_missing_name(self):
        """Test create without name raises error."""
        tool = create_git_branch_tool()

        with pytest.raises(ValueError) as exc_info:
            tool.handler({"action": "create"})

        assert "name required" in str(exc_info.value).lower()


class TestGitCheckoutTool:
    """Tests for git_checkout tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_checkout_tool()

        assert tool.name == "git_checkout"
        assert tool.permission_level == PermissionLevel.CAUTIOUS

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_checkout_branch(self, mock_repo_class):
        """Test checkout branch."""
        mock_repo = MagicMock()
        mock_repo.checkout.return_value = "Switched to branch 'feature'"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_checkout_tool()
        result = tool.handler({"target": "feature"})

        mock_repo.checkout.assert_called_with("feature", create=False)

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_checkout_create(self, mock_repo_class):
        """Test checkout with create flag."""
        mock_repo = MagicMock()
        mock_repo.checkout.return_value = "Switched to new branch"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_checkout_tool()
        tool.handler({"target": "new-feature", "create": True})

        mock_repo.checkout.assert_called_with("new-feature", create=True)


class TestGitAddTool:
    """Tests for git_add tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_add_tool()

        assert tool.name == "git_add"
        assert tool.permission_level == PermissionLevel.CAUTIOUS

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_add_files(self, mock_repo_class):
        """Test adding files."""
        mock_repo = MagicMock()
        mock_repo.add.return_value = "Staged 2 files"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_add_tool()
        result = tool.handler({"files": ["file1.py", "file2.py"]})

        mock_repo.add.assert_called_with(["file1.py", "file2.py"])


class TestGitCommitTool:
    """Tests for git_commit tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_commit_tool()

        assert tool.name == "git_commit"
        assert tool.permission_level == PermissionLevel.CAUTIOUS

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_commit(self, mock_repo_class):
        """Test creating commit."""
        mock_repo = MagicMock()
        mock_repo.commit.return_value = GitCommit(
            hash="abc1234",
            short_hash="abc1234",
            message="Test commit",
            author="John",
            email="john@test.com",
            date="2024-01-15",
        )
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_commit_tool()
        result = tool.handler({"message": "Test commit"})

        mock_repo.commit.assert_called_with("Test commit", all=False)
        assert "abc1234" in result


class TestGitStashTool:
    """Tests for git_stash tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_stash_tool()

        assert tool.name == "git_stash"
        assert tool.permission_level == PermissionLevel.CAUTIOUS

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_list(self, mock_repo_class):
        """Test stash list."""
        mock_repo = MagicMock()
        mock_repo.stash_list.return_value = [
            GitStash(index=0, message="WIP", branch="main"),
        ]
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_stash_tool()
        result = tool.handler({"action": "list"})

        assert "WIP" in result

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_push(self, mock_repo_class):
        """Test stash push."""
        mock_repo = MagicMock()
        mock_repo.stash_push.return_value = "Saved working directory"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_stash_tool()
        result = tool.handler({"action": "push", "message": "Work in progress"})

        mock_repo.stash_push.assert_called_with(message="Work in progress")

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_pop(self, mock_repo_class):
        """Test stash pop."""
        mock_repo = MagicMock()
        mock_repo.stash_pop.return_value = "Applied stash"
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_stash_tool()
        result = tool.handler({"action": "pop"})

        mock_repo.stash_pop.assert_called_with(index=0)


class TestGitBlameTool:
    """Tests for git_blame tool."""

    def test_tool_creation(self):
        """Test tool creation."""
        tool = create_git_blame_tool()

        assert tool.name == "git_blame"
        assert tool.permission_level == PermissionLevel.SAFE

    @patch("codecrew.tools.builtin.git.GitRepository")
    def test_handler_blame(self, mock_repo_class):
        """Test blame."""
        mock_repo = MagicMock()
        mock_repo.blame.return_value = GitBlame(
            file="test.py",
            lines=[
                {"line_num": 1, "commit": "abc1234", "author": "John", "content": "import os"},
            ],
        )
        mock_repo_class.find.return_value = mock_repo

        tool = create_git_blame_tool()
        result = tool.handler({"file": "test.py"})

        assert "test.py" in result
        assert "abc1234" in result


class TestGetGitTools:
    """Tests for get_git_tools function."""

    def test_returns_all_tools(self):
        """Test that all git tools are returned."""
        tools = get_git_tools()

        assert len(tools) == 10
        tool_names = [t.name for t in tools]
        assert "git_status" in tool_names
        assert "git_diff" in tool_names
        assert "git_log" in tool_names
        assert "git_show" in tool_names
        assert "git_branch" in tool_names
        assert "git_checkout" in tool_names
        assert "git_add" in tool_names
        assert "git_commit" in tool_names
        assert "git_stash" in tool_names
        assert "git_blame" in tool_names


class TestRegisterGitTools:
    """Tests for register_git_tools function."""

    def test_registers_all_tools(self):
        """Test that all tools are registered."""
        registry = ToolRegistry()
        register_git_tools(registry)

        assert registry.get("git_status") is not None
        assert registry.get("git_diff") is not None
        assert registry.get("git_log") is not None
        assert registry.get("git_show") is not None
        assert registry.get("git_branch") is not None
        assert registry.get("git_checkout") is not None
        assert registry.get("git_add") is not None
        assert registry.get("git_commit") is not None
        assert registry.get("git_stash") is not None
        assert registry.get("git_blame") is not None
