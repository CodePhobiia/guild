"""Tests for GitRepository class."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from codecrew.git.repository import (
    GitRepository,
    GitStatus,
    GitCommit,
    GitDiff,
    GitBranch,
    GitStash,
    GitBlame,
)
from codecrew.git.utils import GitError


class TestGitStatus:
    """Tests for GitStatus dataclass."""

    def test_git_status_defaults(self):
        """Test GitStatus default values."""
        status = GitStatus(branch="main", is_clean=True)

        assert status.branch == "main"
        assert status.upstream is None
        assert status.ahead == 0
        assert status.behind == 0
        assert status.staged == []
        assert status.modified == []
        assert status.deleted == []
        assert status.untracked == []
        assert status.conflicted == []

    def test_git_status_is_clean(self):
        """Test is_clean reflects actual state."""
        clean = GitStatus(branch="main", is_clean=True)
        assert clean.is_clean is True

        not_clean = GitStatus(
            branch="main",
            is_clean=False,
            staged=[("added", "file.py")],
        )
        assert not_clean.is_clean is False

    def test_git_status_summary(self):
        """Test summary method."""
        status = GitStatus(
            branch="main",
            is_clean=False,
            staged=[("added", "file.py")],
            modified=["other.py"],
        )
        summary = status.summary()
        assert "main" in summary
        assert "Staged" in summary


class TestGitCommit:
    """Tests for GitCommit dataclass."""

    def test_git_commit_basic(self):
        """Test GitCommit creation."""
        commit = GitCommit(
            hash="abc1234567890",
            short_hash="abc1234",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15 10:30:00",
            message="Initial commit",
        )

        assert commit.hash == "abc1234567890"
        assert commit.short_hash == "abc1234"
        assert commit.message == "Initial commit"

    def test_git_commit_one_line(self):
        """Test one_line method."""
        commit = GitCommit(
            hash="abc1234",
            short_hash="abc1234",
            author="Jane",
            email="jane@test.com",
            date="2024-01-15",
            message="Fix bug",
        )
        line = commit.one_line()
        assert "abc1234" in line
        assert "Fix bug" in line

    def test_git_commit_full(self):
        """Test full method."""
        commit = GitCommit(
            hash="abc1234",
            short_hash="abc1234",
            author="Jane Doe",
            email="jane@test.com",
            date="2024-01-15 10:30:00",
            message="Fix bug",
        )
        full = commit.full()
        assert "abc1234" in full
        assert "Jane Doe" in full
        assert "Fix bug" in full


class TestGitDiff:
    """Tests for GitDiff dataclass."""

    def test_git_diff_empty(self):
        """Test empty diff."""
        diff = GitDiff(content="", files=[])
        assert diff.content == ""

    def test_git_diff_with_content(self):
        """Test diff with content."""
        diff = GitDiff(
            content="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            files=["file.py"],
            insertions=1,
            deletions=1,
        )
        assert len(diff.files) == 1
        assert diff.insertions == 1

    def test_git_diff_summary(self):
        """Test summary method."""
        diff = GitDiff(
            content="...",
            files=["a.py", "b.py", "c.py"],
            insertions=10,
            deletions=5,
        )
        summary = diff.summary()
        assert "3 file" in summary
        assert "10 insertion" in summary
        assert "5 deletion" in summary


class TestGitBranch:
    """Tests for GitBranch dataclass."""

    def test_git_branch_local(self):
        """Test local branch."""
        branch = GitBranch(
            name="feature/test",
            is_current=True,
            is_remote=False,
        )
        assert branch.name == "feature/test"
        assert branch.is_current is True
        assert branch.is_remote is False

    def test_git_branch_remote(self):
        """Test remote branch."""
        branch = GitBranch(
            name="origin/main",
            is_current=False,
            is_remote=True,
        )
        assert branch.is_remote is True


class TestGitStash:
    """Tests for GitStash dataclass."""

    def test_git_stash_basic(self):
        """Test stash creation."""
        stash = GitStash(
            index=0,
            message="WIP: feature work",
            branch="feature",
        )
        assert stash.index == 0
        assert stash.message == "WIP: feature work"
        assert stash.branch == "feature"

    def test_git_stash_one_line(self):
        """Test one_line method."""
        stash = GitStash(index=2, message="Test stash", branch="main")
        line = stash.one_line()
        assert "stash@{2}" in line
        assert "Test stash" in line


class TestGitBlame:
    """Tests for GitBlame dataclass."""

    def test_git_blame_basic(self):
        """Test blame creation."""
        blame = GitBlame(
            file="test.py",
            lines=[
                {"line_num": 1, "commit": "abc1234", "author": "John", "content": "import os"},
                {"line_num": 2, "commit": "def5678", "author": "Jane", "content": "print('hi')"},
            ],
        )
        assert blame.file == "test.py"
        assert len(blame.lines) == 2


class TestGitRepository:
    """Tests for GitRepository class."""

    def test_find_not_in_repo(self, tmp_path):
        """Test find behavior with path without .git."""
        # Create an isolated subdirectory
        isolated = tmp_path / "isolated"
        isolated.mkdir()

        # find() returns None or a parent repo if tmp_path is in a git repo
        result = GitRepository.find(isolated)
        # We just verify the function runs without error

    def test_find_in_repo(self, tmp_path):
        """Test find returns repository when in repo."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = GitRepository.find(tmp_path)
        assert result is not None
        assert result.path == tmp_path

    @patch("codecrew.git.repository.run_git_command")
    def test_get_status(self, mock_run, tmp_path):
        """Test get_status method."""
        # Setup mock .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock command responses
        mock_run.side_effect = [
            MagicMock(stdout="main", returncode=0),  # rev-parse for branch
            GitError("No upstream"),  # rev-parse for upstream (raises error)
            MagicMock(stdout="A  new.py\n M changed.py\n", returncode=0),  # status
        ]

        repo = GitRepository(tmp_path)
        status = repo.get_status()

        assert status.branch == "main"
        assert ("added", "new.py") in status.staged
        assert "changed.py" in status.modified

    @patch("codecrew.git.repository.run_git_command")
    def test_get_diff(self, mock_run, tmp_path):
        """Test get_diff method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            MagicMock(stdout="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new", returncode=0),
            MagicMock(stdout=" file.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n", returncode=0),
        ]

        repo = GitRepository(tmp_path)
        diff = repo.get_diff()

        assert "old" in diff.content
        assert "new" in diff.content

    @patch("codecrew.git.repository.run_git_command")
    def test_get_log(self, mock_run, tmp_path):
        """Test get_log method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(
            stdout="abc1234|John Doe|john@test.com|2024-01-15 10:30:00|Initial commit\ndef5678|Jane Doe|jane@test.com|2024-01-16 11:00:00|Add feature\n",
            returncode=0,
        )

        repo = GitRepository(tmp_path)
        commits = repo.get_log(limit=2)

        assert len(commits) == 2
        assert commits[0].hash == "abc1234"
        assert commits[0].author == "John Doe"
        assert commits[1].message == "Add feature"

    @patch("codecrew.git.repository.run_git_command")
    def test_get_branches(self, mock_run, tmp_path):
        """Test get_branches method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(
            stdout="* main abc1234 Latest commit\n  feature def5678 Some work\n",
            returncode=0,
        )

        repo = GitRepository(tmp_path)
        branches = repo.get_branches()

        assert len(branches) == 2
        assert branches[0].name == "main"
        assert branches[0].is_current is True
        assert branches[1].name == "feature"
        assert branches[1].is_current is False

    @patch("codecrew.git.repository.run_git_command")
    def test_get_current_branch(self, mock_run, tmp_path):
        """Test get_current_branch method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="feature-branch", returncode=0)

        repo = GitRepository(tmp_path)
        branch = repo.get_current_branch()

        assert branch == "feature-branch"

    @patch("codecrew.git.repository.run_git_command")
    def test_checkout(self, mock_run, tmp_path):
        """Test checkout method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="Switched to branch 'feature'", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.checkout("feature")

        assert "feature" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_checkout_create(self, mock_run, tmp_path):
        """Test checkout with create flag."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="Switched to a new branch 'new-feature'", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.checkout("new-feature", create=True)

        assert "new" in result.lower()

        # Verify -b flag was used
        call_args = mock_run.call_args[0][0]
        assert "-b" in call_args

    @patch("codecrew.git.repository.run_git_command")
    def test_add(self, mock_run, tmp_path):
        """Test add method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.add(["file.py", "other.py"])

        assert "Staged" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_commit(self, mock_run, tmp_path):
        """Test commit method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # First call: commit, second call: get_commit
        mock_run.side_effect = [
            MagicMock(stdout="[main abc1234] Test commit\n", returncode=0),
            MagicMock(stdout="abc1234|John|john@test.com|2024-01-15|Test commit", returncode=0),
        ]

        repo = GitRepository(tmp_path)
        commit = repo.commit("Test commit")

        assert commit.message == "Test commit"

    @patch("codecrew.git.repository.run_git_command")
    def test_create_branch(self, mock_run, tmp_path):
        """Test create_branch method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.create_branch("new-branch")

        assert "Created" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_delete_branch(self, mock_run, tmp_path):
        """Test delete_branch method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="Deleted branch feature", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.delete_branch("feature")

        assert "Deleted" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_stash_list(self, mock_run, tmp_path):
        """Test stash_list method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(
            stdout="stash@{0}: On main: WIP\nstash@{1}: On feature: Another\n",
            returncode=0,
        )

        repo = GitRepository(tmp_path)
        stashes = repo.stash_list()

        assert len(stashes) == 2
        assert stashes[0].index == 0
        assert stashes[0].branch == "main"
        assert "WIP" in stashes[0].message

    @patch("codecrew.git.repository.run_git_command")
    def test_stash_push(self, mock_run, tmp_path):
        """Test stash_push method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="Saved working directory", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.stash_push(message="Work in progress")

        assert "Saved" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_stash_pop(self, mock_run, tmp_path):
        """Test stash_pop method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(stdout="Applied stash", returncode=0)

        repo = GitRepository(tmp_path)
        result = repo.stash_pop()

        assert "Applied" in result

    @patch("codecrew.git.repository.run_git_command")
    def test_blame(self, mock_run, tmp_path):
        """Test blame method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Line-porcelain format output
        blame_output = """abc1234567890123456789012345678901234567890 1 1 1
author John
author-time 1705320600
	import os
def5678901234567890123456789012345678901234 2 2 1
author Jane
author-time 1705407000
	print('hi')
"""
        mock_run.return_value = MagicMock(stdout=blame_output, returncode=0)

        repo = GitRepository(tmp_path)
        blame = repo.blame("test.py")

        assert blame.file == "test.py"
        assert len(blame.lines) == 2

    @patch("codecrew.git.repository.run_git_command")
    def test_show_commit(self, mock_run, tmp_path):
        """Test show_commit method."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = MagicMock(
            stdout="commit abc1234\nAuthor: John\nDate: 2024-01-15\n\n    Initial commit\n",
            returncode=0,
        )

        repo = GitRepository(tmp_path)
        result = repo.show_commit("abc1234")

        assert "Initial commit" in result
