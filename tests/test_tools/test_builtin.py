"""Tests for built-in tools."""

import os
import tempfile
from pathlib import Path

import pytest

from codecrew.tools.builtin import (
    get_builtin_tools,
    register_builtin_tools,
)
from codecrew.tools.builtin.files import (
    PathAccessError,
    create_edit_file_tool,
    create_list_directory_tool,
    create_read_file_tool,
    create_search_files_tool,
    create_write_file_tool,
)
from codecrew.tools.builtin.shell import (
    create_execute_command_tool,
    get_command_permission_level,
)
from codecrew.tools.permissions import PermissionLevel
from codecrew.tools.registry import ToolRegistry


class TestBuiltinToolRegistration:
    """Tests for registering built-in tools."""

    def test_register_builtin_tools(self):
        """Test registering all built-in tools."""
        registry = ToolRegistry()
        register_builtin_tools(registry)

        # Check that all expected tools are registered
        expected_tools = [
            "read_file",
            "write_file",
            "edit_file",
            "list_directory",
            "search_files",
            "execute_command",
        ]

        for tool_name in expected_tools:
            assert registry.has(tool_name), f"Tool {tool_name} not registered"

    def test_get_builtin_tools(self):
        """Test getting built-in tools as a list."""
        tools = get_builtin_tools()

        # 6 file/shell tools + 10 git tools = 16 total
        assert len(tools) == 16

        tool_names = [t.name for t in tools]
        assert "read_file" in tool_names
        assert "execute_command" in tool_names
        # Git tools
        assert "git_status" in tool_names
        assert "git_diff" in tool_names
        assert "git_commit" in tool_names


class TestReadFileTool:
    """Tests for the read_file tool."""

    def test_read_existing_file(self, tmp_path):
        """Test reading an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        tool = create_read_file_tool(working_directory=str(tmp_path))

        result = tool.handler({"path": "test.txt"})

        assert result == "Hello, World!"

    def test_read_absolute_path(self, tmp_path):
        """Test reading with absolute path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content")

        tool = create_read_file_tool()

        result = tool.handler({"path": str(test_file)})

        assert result == "Content"

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading a nonexistent file raises."""
        tool = create_read_file_tool(working_directory=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            tool.handler({"path": "nonexistent.txt"})

    def test_read_directory_raises(self, tmp_path):
        """Test reading a directory raises."""
        tool = create_read_file_tool(working_directory=str(tmp_path))

        with pytest.raises(ValueError, match="not a file"):
            tool.handler({"path": str(tmp_path)})

    def test_read_file_too_large(self, tmp_path):
        """Test reading a file that's too large raises."""
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 2000)  # 2KB

        tool = create_read_file_tool(
            working_directory=str(tmp_path),
            max_file_size=1000,  # 1KB limit
        )

        with pytest.raises(ValueError, match="too large"):
            tool.handler({"path": "large.txt"})

    def test_read_file_outside_allowed_paths(self, tmp_path):
        """Test reading outside allowed paths raises."""
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        test_file = other_dir / "test.txt"
        test_file.write_text("Secret")

        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        tool = create_read_file_tool(allowed_paths=[str(allowed_dir)])

        with pytest.raises(PathAccessError):
            tool.handler({"path": str(test_file)})


class TestWriteFileTool:
    """Tests for the write_file tool."""

    def test_write_new_file(self, tmp_path):
        """Test writing a new file."""
        tool = create_write_file_tool(working_directory=str(tmp_path))

        result = tool.handler({"path": "new.txt", "content": "Hello!"})

        assert "Successfully wrote" in result
        assert (tmp_path / "new.txt").read_text() == "Hello!"

    def test_write_overwrite_file(self, tmp_path):
        """Test overwriting an existing file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Old content")

        tool = create_write_file_tool(working_directory=str(tmp_path))

        tool.handler({"path": "existing.txt", "content": "New content"})

        assert test_file.read_text() == "New content"

    def test_write_creates_directories(self, tmp_path):
        """Test that directories are created as needed."""
        tool = create_write_file_tool(
            working_directory=str(tmp_path),
            create_directories=True,
        )

        tool.handler({"path": "subdir/deep/file.txt", "content": "Content"})

        assert (tmp_path / "subdir" / "deep" / "file.txt").read_text() == "Content"

    def test_write_permission_level(self, tmp_path):
        """Test that write_file has CAUTIOUS permission level."""
        tool = create_write_file_tool(working_directory=str(tmp_path))

        assert tool.permission_level == PermissionLevel.CAUTIOUS


class TestEditFileTool:
    """Tests for the edit_file tool."""

    def test_edit_single_replacement(self, tmp_path):
        """Test making a single edit."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        tool = create_edit_file_tool(working_directory=str(tmp_path))

        result = tool.handler({
            "path": "test.txt",
            "edits": [{"old_text": "World", "new_text": "Python"}],
        })

        assert "Successfully made 1 edit" in result
        assert test_file.read_text() == "Hello, Python!"

    def test_edit_multiple_replacements(self, tmp_path):
        """Test making multiple edits."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("foo bar baz")

        tool = create_edit_file_tool(working_directory=str(tmp_path))

        result = tool.handler({
            "path": "test.txt",
            "edits": [
                {"old_text": "foo", "new_text": "FOO"},
                {"old_text": "baz", "new_text": "BAZ"},
            ],
        })

        assert "2 edit" in result
        assert test_file.read_text() == "FOO bar BAZ"

    def test_edit_text_not_found(self, tmp_path):
        """Test editing when text is not found."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        tool = create_edit_file_tool(working_directory=str(tmp_path))

        with pytest.raises(ValueError, match="not found"):
            tool.handler({
                "path": "test.txt",
                "edits": [{"old_text": "nonexistent", "new_text": "replacement"}],
            })

    def test_edit_nonexistent_file(self, tmp_path):
        """Test editing a nonexistent file."""
        tool = create_edit_file_tool(working_directory=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            tool.handler({
                "path": "nonexistent.txt",
                "edits": [{"old_text": "a", "new_text": "b"}],
            })


class TestListDirectoryTool:
    """Tests for the list_directory tool."""

    def test_list_directory(self, tmp_path):
        """Test listing directory contents."""
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        (tmp_path / "subdir").mkdir()

        tool = create_list_directory_tool(working_directory=str(tmp_path))

        result = tool.handler({"path": "."})

        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "subdir" in result
        assert "dir:" in result  # subdir should be marked as directory

    def test_list_directory_recursive(self, tmp_path):
        """Test listing directory recursively."""
        (tmp_path / "file1.txt").write_text("1")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        tool = create_list_directory_tool(working_directory=str(tmp_path))

        result = tool.handler({"path": ".", "recursive": True})

        assert "file1.txt" in result
        assert "nested.txt" in result

    def test_list_nonexistent_directory(self, tmp_path):
        """Test listing nonexistent directory."""
        tool = create_list_directory_tool(working_directory=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            tool.handler({"path": "nonexistent"})

    def test_list_file_raises(self, tmp_path):
        """Test listing a file (not directory) raises."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        tool = create_list_directory_tool(working_directory=str(tmp_path))

        with pytest.raises(ValueError, match="not a directory"):
            tool.handler({"path": "file.txt"})


class TestSearchFilesTool:
    """Tests for the search_files tool."""

    def test_search_simple_pattern(self, tmp_path):
        """Test searching for a simple pattern."""
        (tmp_path / "file1.txt").write_text("Hello, World!")
        (tmp_path / "file2.txt").write_text("Goodbye, World!")

        tool = create_search_files_tool(working_directory=str(tmp_path))

        result = tool.handler({"pattern": "World"})

        assert "2 match" in result
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_search_regex_pattern(self, tmp_path):
        """Test searching with regex pattern."""
        (tmp_path / "test.py").write_text("def foo():\n    pass\n\ndef bar():\n    pass")

        tool = create_search_files_tool(working_directory=str(tmp_path))

        result = tool.handler({"pattern": r"def \w+\(\)"})

        assert "foo()" in result
        assert "bar()" in result

    def test_search_with_file_pattern(self, tmp_path):
        """Test searching with file pattern filter."""
        (tmp_path / "file.py").write_text("python code")
        (tmp_path / "file.txt").write_text("python text")

        tool = create_search_files_tool(working_directory=str(tmp_path))

        result = tool.handler({
            "pattern": "python",
            "file_pattern": "*.py",
        })

        assert "file.py" in result
        # file.txt should not be in results (filtered out)

    def test_search_no_matches(self, tmp_path):
        """Test searching with no matches."""
        (tmp_path / "file.txt").write_text("Hello, World!")

        tool = create_search_files_tool(working_directory=str(tmp_path))

        result = tool.handler({"pattern": "nonexistent"})

        assert "No matches found" in result

    def test_search_invalid_regex(self, tmp_path):
        """Test searching with invalid regex raises."""
        (tmp_path / "file.txt").write_text("test")

        tool = create_search_files_tool(working_directory=str(tmp_path))

        with pytest.raises(ValueError, match="Invalid regex"):
            tool.handler({"pattern": "[invalid"})


class TestExecuteCommandTool:
    """Tests for the execute_command tool."""

    def test_execute_simple_command(self, tmp_path):
        """Test executing a simple command."""
        tool = create_execute_command_tool(working_directory=str(tmp_path))

        # Use a cross-platform command
        if os.name == "nt":
            result = tool.handler({"command": "echo Hello"})
        else:
            result = tool.handler({"command": "echo Hello"})

        assert "Hello" in result
        assert "Exit code: 0" in result

    def test_execute_command_with_cwd(self, tmp_path):
        """Test executing command with specific working directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        tool = create_execute_command_tool(working_directory=str(tmp_path))

        if os.name == "nt":
            result = tool.handler({"command": "cd", "cwd": "subdir"})
        else:
            result = tool.handler({"command": "pwd", "cwd": "subdir"})

        assert "subdir" in result

    def test_execute_command_with_error(self, tmp_path):
        """Test executing a command that fails."""
        tool = create_execute_command_tool(working_directory=str(tmp_path))

        # Use a command that's likely to fail
        if os.name == "nt":
            result = tool.handler({"command": "nonexistent_command_xyz"})
        else:
            result = tool.handler({"command": "false"})

        assert "Exit code:" in result
        # Exit code should not be 0

    def test_execute_command_dangerous_level(self):
        """Test that execute_command has DANGEROUS permission level."""
        tool = create_execute_command_tool()

        assert tool.permission_level == PermissionLevel.DANGEROUS

    def test_blocked_command(self, tmp_path):
        """Test that blocked commands are rejected."""
        tool = create_execute_command_tool(working_directory=str(tmp_path))

        with pytest.raises(PermissionError, match="blocked"):
            tool.handler({"command": "rm -rf /"})


class TestCommandPermissionLevel:
    """Tests for command permission level detection."""

    def test_safe_commands(self):
        """Test that safe commands are detected."""
        safe_commands = ["ls", "pwd", "echo hello", "git status", "cat file.txt"]

        for cmd in safe_commands:
            level = get_command_permission_level(cmd)
            assert level == PermissionLevel.SAFE, f"Expected {cmd} to be SAFE"

    def test_dangerous_commands(self):
        """Test that dangerous commands are detected."""
        dangerous_commands = ["rm file", "sudo apt install", "git push", "curl http://example.com"]

        for cmd in dangerous_commands:
            level = get_command_permission_level(cmd)
            assert level == PermissionLevel.DANGEROUS, f"Expected {cmd} to be DANGEROUS"

    def test_blocked_commands(self):
        """Test that blocked commands are detected."""
        blocked_commands = ["rm -rf /", "rm -rf /*"]

        for cmd in blocked_commands:
            level = get_command_permission_level(cmd)
            assert level == PermissionLevel.BLOCKED, f"Expected {cmd} to be BLOCKED"

    def test_cautious_default(self):
        """Test that unknown commands default to CAUTIOUS."""
        level = get_command_permission_level("some_unknown_command --flag")
        assert level == PermissionLevel.CAUTIOUS
