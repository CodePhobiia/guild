# Phase 7: Commands and User Interaction

## Overview
Phase 7 enhances the user interaction experience with persistent history, keyboard shortcuts, improved navigation, and advanced command features.

## Goals
1. Persistent command/input history across sessions
2. Configurable keyboard shortcuts
3. Message navigation and search
4. Clipboard support
5. Enhanced session management
6. Improved help system

## Architecture

### New Files

```
codecrew/ui/
├── history.py           # Persistent history manager
├── keybindings.py       # Keyboard binding system
├── navigation.py        # Message/conversation navigation
└── clipboard.py         # Clipboard operations

tests/test_ui/
├── test_history.py      # History manager tests
├── test_keybindings.py  # Keyboard binding tests
└── test_navigation.py   # Navigation tests
```

### Modified Files
- `codecrew/ui/components/input_area.py` - Integrate history & keybindings
- `codecrew/ui/components/message_list.py` - Add navigation support
- `codecrew/ui/handlers/commands.py` - New commands, enhanced help
- `codecrew/ui/app.py` - Integrate new systems
- `codecrew/conversation/persistence.py` - History table migration

## Implementation Details

### 1. Persistent History Manager (`history.py`)

```python
@dataclass
class HistoryEntry:
    id: str
    content: str
    timestamp: datetime
    entry_type: str  # "message" | "command"
    session_id: Optional[str]

class HistoryManager:
    """Manages persistent input history with database storage."""

    async def add_entry(self, content: str, entry_type: str) -> None
    async def get_recent(self, limit: int = 100) -> list[HistoryEntry]
    async def search(self, query: str, limit: int = 50) -> list[HistoryEntry]
    async def get_by_type(self, entry_type: str) -> list[HistoryEntry]
    async def clear(self, older_than: Optional[datetime] = None) -> int
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS input_history (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    session_id TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX idx_history_timestamp ON input_history(timestamp DESC);
CREATE INDEX idx_history_type ON input_history(entry_type);
```

### 2. Keyboard Bindings System (`keybindings.py`)

```python
@dataclass
class KeyBinding:
    key: str           # e.g., "c-l", "c-r", "f1"
    action: str        # e.g., "clear_screen", "search_history"
    description: str
    category: str      # "navigation", "editing", "commands"

class KeyBindingManager:
    """Manages keyboard shortcuts with customization support."""

    DEFAULT_BINDINGS = {
        "c-l": ("clear_screen", "Clear the screen"),
        "c-r": ("search_history", "Search command history"),
        "c-p": ("previous_history", "Previous history entry"),
        "c-n": ("next_history", "Next history entry"),
        "c-u": ("clear_line", "Clear current line"),
        "c-w": ("delete_word", "Delete previous word"),
        "f1": ("show_help", "Show help"),
        "f2": ("show_commands", "Show all commands"),
        "f3": ("toggle_compact", "Toggle compact mode"),
        "f5": ("refresh", "Refresh display"),
        "pageup": ("scroll_up", "Scroll messages up"),
        "pagedown": ("scroll_down", "Scroll messages down"),
        "home": ("scroll_top", "Scroll to top"),
        "end": ("scroll_bottom", "Scroll to bottom"),
    }

    def get_bindings(self) -> dict[str, KeyBinding]
    def set_binding(self, key: str, action: str) -> None
    def get_action(self, key: str) -> Optional[str]
    def create_prompt_toolkit_bindings(self) -> KeyBindings
```

### 3. Message Navigation System (`navigation.py`)

```python
@dataclass
class NavigationState:
    scroll_offset: int = 0
    selected_message: Optional[int] = None
    search_query: Optional[str] = None
    search_results: list[int] = field(default_factory=list)
    search_index: int = 0

class NavigationManager:
    """Manages message list navigation and search."""

    def __init__(self, message_list: MessageList):
        self.message_list = message_list
        self.state = NavigationState()

    def scroll_up(self, lines: int = 1) -> None
    def scroll_down(self, lines: int = 1) -> None
    def scroll_to_top(self) -> None
    def scroll_to_bottom(self) -> None
    def scroll_page_up(self) -> None
    def scroll_page_down(self) -> None

    def search(self, query: str) -> int  # returns match count
    def next_match(self) -> Optional[int]
    def prev_match(self) -> Optional[int]
    def clear_search(self) -> None

    def select_message(self, index: int) -> None
    def get_selected_message(self) -> Optional[MessageItem]
    def copy_selected(self) -> str
```

### 4. Clipboard Support (`clipboard.py`)

```python
class ClipboardManager:
    """Cross-platform clipboard operations."""

    @staticmethod
    def copy(text: str) -> bool:
        """Copy text to clipboard. Returns success status."""

    @staticmethod
    def paste() -> Optional[str]:
        """Get text from clipboard."""

    @staticmethod
    def is_available() -> bool:
        """Check if clipboard is available."""
```

Uses `pyperclip` for cross-platform support (already a common dependency).

### 5. Enhanced Commands

**New Commands:**
- `/history [limit]` - Show input history
- `/search <query>` - Search messages
- `/copy [msg_id]` - Copy message to clipboard
- `/goto <msg_id>` - Jump to message
- `/keys` - Show keyboard shortcuts
- `/bind <key> <action>` - Customize binding
- `/unbind <key>` - Remove binding
- `/alias <name> <command>` - Create command alias
- `/unalias <name>` - Remove alias

**Enhanced Help System:**
```python
COMMAND_GROUPS = {
    "Session": ["/new", "/sessions", "/load", "/save", "/export"],
    "Display": ["/clear", "/compact", "/decisions", "/theme"],
    "Navigation": ["/search", "/goto", "/history"],
    "Information": ["/help", "/models", "/config", "/stats", "/keys"],
    "Messages": ["/pin", "/unpin", "/copy"],
}
```

### 6. Updated InputArea Integration

```python
class InputArea:
    def __init__(
        self,
        theme: Theme,
        history_manager: HistoryManager,
        keybinding_manager: KeyBindingManager,
        on_submit: Callable,
        ...
    ):
        self.history_manager = history_manager
        self.keybinding_manager = keybinding_manager

        # Use persistent history
        self._history = self._create_persistent_history()

        # Apply custom keybindings
        self._key_bindings = keybinding_manager.create_prompt_toolkit_bindings()
```

## Migration

Add to `codecrew/conversation/migrations.py`:

```python
MIGRATION_003_HISTORY = """
CREATE TABLE IF NOT EXISTS input_history (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    session_id TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON input_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_history_type ON input_history(entry_type);

CREATE TABLE IF NOT EXISTS command_aliases (
    name TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS key_bindings (
    key TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
```

## Testing Plan

### Unit Tests

1. **test_history.py**
   - Test add/retrieve entries
   - Test search functionality
   - Test type filtering
   - Test cleanup operations
   - Test database persistence

2. **test_keybindings.py**
   - Test default bindings
   - Test custom bindings
   - Test binding removal
   - Test prompt_toolkit integration
   - Test action dispatch

3. **test_navigation.py**
   - Test scroll operations
   - Test search functionality
   - Test message selection
   - Test boundary conditions

### Integration Tests
- Test history persistence across app restarts
- Test keybindings during input
- Test navigation during conversation

## Dependencies

Add to `pyproject.toml`:
```toml
pyperclip = "^1.8"  # Cross-platform clipboard
```

## Implementation Order

1. **Phase 7.1**: History Manager
   - Create `history.py`
   - Add database migration
   - Integrate with InputArea
   - Write tests

2. **Phase 7.2**: Keyboard Bindings
   - Create `keybindings.py`
   - Define default bindings
   - Integrate with prompt_toolkit
   - Write tests

3. **Phase 7.3**: Navigation
   - Create `navigation.py`
   - Add scroll support to MessageList
   - Implement search
   - Write tests

4. **Phase 7.4**: Clipboard & Commands
   - Create `clipboard.py`
   - Add new commands
   - Enhance help system
   - Write tests

5. **Phase 7.5**: Integration
   - Update app.py
   - Update commands.py
   - Full integration testing
   - Documentation

## Success Criteria

- [ ] Input history persists across sessions
- [ ] History search works with Ctrl+R
- [ ] All default keyboard shortcuts function
- [ ] Message scrolling with Page Up/Down
- [ ] Message search with highlighting
- [ ] Clipboard copy/paste works
- [ ] All new commands functional
- [ ] Help shows grouped commands
- [ ] 50+ new tests passing
- [ ] Total tests > 550
