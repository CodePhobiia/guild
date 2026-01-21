"""Tests for the keybindings module."""

import tempfile
from pathlib import Path

import pytest

from codecrew.ui.keybindings import DEFAULT_BINDINGS, KeyBinding, KeyBindingManager


class TestKeyBinding:
    """Tests for KeyBinding dataclass."""

    def test_create_binding(self):
        """Test creating a key binding."""
        binding = KeyBinding(
            key="c-l",
            action="clear_screen",
            description="Clear the screen",
            category="display",
        )

        assert binding.key == "c-l"
        assert binding.action == "clear_screen"
        assert binding.description == "Clear the screen"
        assert binding.category == "display"

    def test_display_key_ctrl(self):
        """Test display key formatting for Ctrl keys."""
        binding = KeyBinding(key="c-l", action="test", description="Test", category="test")
        assert binding.display_key == "Ctrl+L"

    def test_display_key_shift(self):
        """Test display key formatting for Shift keys."""
        binding = KeyBinding(key="s-tab", action="test", description="Test", category="test")
        assert binding.display_key == "Shift+TAB"

    def test_display_key_function(self):
        """Test display key formatting for function keys."""
        binding = KeyBinding(key="f1", action="test", description="Test", category="test")
        assert binding.display_key == "f1"

    def test_display_key_pageup(self):
        """Test display key formatting for Page Up."""
        binding = KeyBinding(key="pageup", action="test", description="Test", category="test")
        assert binding.display_key == "Page Up"

    def test_display_key_pagedown(self):
        """Test display key formatting for Page Down."""
        binding = KeyBinding(key="pagedown", action="test", description="Test", category="test")
        assert binding.display_key == "Page Down"

    def test_display_key_escape(self):
        """Test display key formatting for Escape."""
        binding = KeyBinding(key="escape", action="test", description="Test", category="test")
        assert binding.display_key == "Esc"


class TestDefaultBindings:
    """Tests for default bindings constant."""

    def test_default_bindings_exist(self):
        """Test that default bindings are defined."""
        assert DEFAULT_BINDINGS is not None
        assert len(DEFAULT_BINDINGS) > 0

    def test_default_bindings_have_required_keys(self):
        """Test that essential key bindings are present."""
        required_keys = ["c-l", "c-r", "f1", "pageup", "pagedown"]
        for key in required_keys:
            assert key in DEFAULT_BINDINGS, f"Missing binding for {key}"

    def test_default_bindings_format(self):
        """Test that default bindings have correct format."""
        for key, value in DEFAULT_BINDINGS.items():
            assert isinstance(value, tuple), f"Binding for {key} should be a tuple"
            assert len(value) == 3, f"Binding for {key} should have 3 elements"
            action, description, category = value
            assert isinstance(action, str)
            assert isinstance(description, str)
            assert isinstance(category, str)

    def test_categories_are_valid(self):
        """Test that all categories are valid."""
        valid_categories = {"display", "navigation", "editing", "session"}
        for key, (_, _, category) in DEFAULT_BINDINGS.items():
            assert category in valid_categories, f"Invalid category '{category}' for {key}"


class TestKeyBindingManager:
    """Tests for KeyBindingManager class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    async def db_with_tables(self, temp_db):
        """Create a database with the required tables."""
        import aiosqlite

        async with aiosqlite.connect(temp_db) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS key_bindings (
                    key TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await conn.commit()

        return temp_db

    @pytest.fixture
    def manager(self):
        """Create a KeyBindingManager without database."""
        return KeyBindingManager(db_path=None)

    @pytest.fixture
    def manager_with_db(self, db_with_tables):
        """Create a KeyBindingManager with database."""
        return KeyBindingManager(db_path=db_with_tables)

    def test_load_defaults(self, manager):
        """Test that defaults are loaded on init."""
        bindings = manager.get_all_bindings()
        assert len(bindings) > 0
        assert "c-l" in bindings

    def test_get_binding(self, manager):
        """Test getting a specific binding."""
        binding = manager.get_binding("c-l")
        assert binding is not None
        assert binding.action == "clear_screen"

    def test_get_binding_not_found(self, manager):
        """Test getting a non-existent binding."""
        binding = manager.get_binding("nonexistent")
        assert binding is None

    def test_get_action(self, manager):
        """Test getting action for a key."""
        action = manager.get_action("c-l")
        assert action == "clear_screen"

    def test_get_action_not_found(self, manager):
        """Test getting action for non-existent key."""
        action = manager.get_action("nonexistent")
        assert action is None

    def test_set_binding(self, manager):
        """Test setting a binding in memory."""
        manager.set_binding(
            key="c-x",
            action="custom_action",
            description="Custom action",
            category="custom",
        )

        binding = manager.get_binding("c-x")
        assert binding is not None
        assert binding.action == "custom_action"
        assert binding.category == "custom"

    def test_set_binding_override_default(self, manager):
        """Test overriding a default binding."""
        original = manager.get_action("c-l")
        assert original == "clear_screen"

        manager.set_binding("c-l", "new_action")
        assert manager.get_action("c-l") == "new_action"

    def test_get_all_bindings(self, manager):
        """Test getting all bindings."""
        bindings = manager.get_all_bindings()
        assert isinstance(bindings, dict)
        assert len(bindings) == len(DEFAULT_BINDINGS)

    def test_get_bindings_by_category(self, manager):
        """Test getting bindings grouped by category."""
        by_category = manager.get_bindings_by_category()

        assert "display" in by_category
        assert "navigation" in by_category
        assert "editing" in by_category
        assert "session" in by_category

        # Check that bindings are in correct categories
        for binding in by_category["display"]:
            assert binding.category == "display"

    def test_register_handler(self, manager):
        """Test registering an action handler."""
        handler_called = False

        def handler():
            nonlocal handler_called
            handler_called = True

        manager.register_handler("test_action", handler)
        retrieved = manager.get_handler("test_action")

        assert retrieved is not None
        retrieved()
        assert handler_called

    def test_get_handler_not_found(self, manager):
        """Test getting non-existent handler."""
        handler = manager.get_handler("nonexistent")
        assert handler is None

    @pytest.mark.asyncio
    async def test_save_binding(self, manager_with_db):
        """Test saving a binding to database."""
        await manager_with_db.save_binding("c-x", "custom_action")

        # Verify it was saved by loading custom bindings
        import aiosqlite

        async with aiosqlite.connect(manager_with_db.db_path) as conn:
            cursor = await conn.execute("SELECT action FROM key_bindings WHERE key = ?", ("c-x",))
            row = await cursor.fetchone()

        assert row is not None
        assert row[0] == "custom_action"

    @pytest.mark.asyncio
    async def test_load_custom_bindings(self, manager_with_db):
        """Test loading custom bindings from database."""
        import aiosqlite
        from datetime import datetime, timezone

        # Insert a custom binding
        async with aiosqlite.connect(manager_with_db.db_path) as conn:
            await conn.execute(
                "INSERT INTO key_bindings (key, action, updated_at) VALUES (?, ?, ?)",
                ("c-l", "custom_clear", datetime.now(timezone.utc).isoformat()),
            )
            await conn.commit()

        # Load custom bindings
        await manager_with_db.load_custom_bindings()

        assert manager_with_db.get_action("c-l") == "custom_clear"

    @pytest.mark.asyncio
    async def test_remove_binding(self, manager_with_db):
        """Test removing a custom binding."""
        # Set a custom binding
        manager_with_db.set_binding("c-x", "custom_action")
        await manager_with_db.save_binding("c-x", "custom_action")

        # Remove it
        result = await manager_with_db.remove_binding("c-x")
        assert result is True

        # Verify it's gone
        binding = manager_with_db.get_binding("c-x")
        assert binding is None

    @pytest.mark.asyncio
    async def test_remove_binding_resets_to_default(self, manager_with_db):
        """Test that removing a default binding resets it."""
        # Override a default
        manager_with_db.set_binding("c-l", "custom_action")

        # Remove the custom binding
        result = await manager_with_db.remove_binding("c-l")
        assert result is True

        # Should be reset to default
        assert manager_with_db.get_action("c-l") == "clear_screen"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_binding(self, manager_with_db):
        """Test removing a non-existent binding."""
        result = await manager_with_db.remove_binding("nonexistent")
        assert result is False

    def test_format_bindings_help(self, manager):
        """Test formatting bindings as help text."""
        help_text = manager.format_bindings_help()

        assert "Keyboard Shortcuts" in help_text
        assert "Display" in help_text
        assert "Navigation" in help_text
        assert "Ctrl+" in help_text or "c-" in help_text

    def test_create_prompt_toolkit_bindings(self, manager):
        """Test creating prompt_toolkit bindings."""
        kb = manager.create_prompt_toolkit_bindings()
        assert kb is not None
        # prompt_toolkit KeyBindings object should have bindings
        assert len(kb.bindings) > 0

    def test_create_prompt_toolkit_bindings_with_callback(self, manager):
        """Test creating bindings with action callback."""
        actions_called = []

        def callback(action):
            actions_called.append(action)

        kb = manager.create_prompt_toolkit_bindings(action_callback=callback)
        assert kb is not None

    @pytest.mark.asyncio
    async def test_load_custom_bindings_without_db(self, manager):
        """Test that load_custom_bindings does nothing without a database."""
        # Should not raise
        await manager.load_custom_bindings()
        # Bindings should still be defaults
        assert manager.get_action("c-l") == "clear_screen"

    @pytest.mark.asyncio
    async def test_save_binding_without_db(self, manager):
        """Test that save_binding does nothing without a database."""
        # Should not raise
        await manager.save_binding("c-x", "test")
        # Memory binding should not be affected
        assert manager.get_binding("c-x") is None
