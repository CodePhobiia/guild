# Phase 6: Rich TUI Development - Implementation Plan

## Overview

Phase 6 transforms CodeCrew from a placeholder CLI into a fully interactive terminal UI. The TUI will handle real-time streaming, multi-model conversations, tool execution visualization, and session management.

## Architecture

### File Structure

```
codecrew/ui/
├── __init__.py              # Package exports
├── app.py                   # Main ChatApp class (entry point)
├── theme.py                 # Theme definitions and color schemes
├── components/
│   ├── __init__.py          # Component exports
│   ├── header.py            # Header bar (session info, models)
│   ├── message_list.py      # Scrollable message display
│   ├── message.py           # Individual message rendering
│   ├── input_area.py        # User input with @mention completion
│   ├── status_bar.py        # Token usage, cost, status
│   ├── spinner.py           # Thinking/executing indicators
│   └── tool_panel.py        # Tool call visualization
├── dialogs/
│   ├── __init__.py          # Dialog exports
│   ├── permission.py        # Tool permission confirmation
│   ├── session_picker.py    # Session selection dialog
│   └── help.py              # Help/commands overlay
└── handlers/
    ├── __init__.py          # Handler exports
    ├── events.py            # Orchestrator event handlers
    ├── commands.py          # Slash command handlers
    └── keybindings.py       # Keyboard shortcut definitions
```

## Implementation Phases

### Phase 6.1: Core Foundation

**Files to create:**
- `codecrew/ui/__init__.py` - Package exports
- `codecrew/ui/theme.py` - Theme system with model colors
- `codecrew/ui/app.py` - Main ChatApp class

**Key classes:**
```python
# theme.py
class Theme:
    """Color scheme and styling definitions."""
    model_colors: dict[str, str]  # claude: orange3, gpt: green, etc.
    message_styles: dict[str, Style]
    ui_styles: dict[str, Style]

THEMES = {
    "default": Theme(...),
    "minimal": Theme(...),
    "colorblind": Theme(...),
}

# app.py
class ChatApp:
    """Main TUI application."""
    def __init__(self, settings: Settings, orchestrator: ToolEnabledOrchestrator)
    async def run(self) -> None
    async def process_input(self, text: str) -> None
    async def handle_event(self, event: OrchestratorEvent) -> None
```

### Phase 6.2: Message Display

**Files to create:**
- `codecrew/ui/components/message.py` - Message rendering
- `codecrew/ui/components/message_list.py` - Message list container
- `codecrew/ui/components/spinner.py` - Loading indicators

**Features:**
- Markdown rendering with syntax highlighting
- Model-colored badges (Claude, GPT, etc.)
- Real-time streaming display
- Thinking/typing indicators
- Pinned message indicators

### Phase 6.3: Input Handling

**Files to create:**
- `codecrew/ui/components/input_area.py` - Input component
- `codecrew/ui/handlers/keybindings.py` - Key bindings
- `codecrew/ui/handlers/commands.py` - Slash commands

**Features:**
- Multi-line input support
- @mention autocomplete (@claude, @gpt, @gemini, @grok, @all)
- Command completion (/help, /quit, /clear, /sessions, /pin, etc.)
- History navigation (up/down arrows)
- Ctrl+C to cancel, Ctrl+D to quit

**Slash Commands:**
```
/help          - Show help
/quit, /exit   - Exit CodeCrew
/clear         - Clear screen
/new           - Start new session
/sessions      - List sessions
/load <id>     - Load session
/export        - Export current session
/pin <n>       - Pin message n
/unpin <n>     - Unpin message n
/stats         - Show conversation stats
/models        - Show model status
/config        - Show configuration
```

### Phase 6.4: Tool Visualization

**Files to create:**
- `codecrew/ui/components/tool_panel.py` - Tool call display
- `codecrew/ui/dialogs/permission.py` - Permission dialog

**Features:**
- Collapsible tool call panels
- Tool name, parameters, and results display
- Execution time and status indicators
- Permission confirmation dialogs (Y/N/Always/Never)
- File diff visualization for edit operations

### Phase 6.5: Layout and Status

**Files to create:**
- `codecrew/ui/components/header.py` - Header bar
- `codecrew/ui/components/status_bar.py` - Status bar

**Header displays:**
- Session name and ID
- Available models (colored indicators)
- Current project path

**Status bar displays:**
- Token usage (current/max)
- Estimated cost
- Active model indicator
- Last save time

### Phase 6.6: Session Management UI

**Files to create:**
- `codecrew/ui/dialogs/session_picker.py` - Session picker
- `codecrew/ui/dialogs/help.py` - Help overlay

**Features:**
- Session list with search
- Quick session switching
- Session preview
- Delete/archive confirmation

### Phase 6.7: Event Handling Integration

**Files to create:**
- `codecrew/ui/handlers/events.py` - Event handler mapping

**Event handling:**
```python
async def handle_event(self, event: OrchestratorEvent) -> None:
    handlers = {
        EventType.THINKING: self._on_thinking,
        EventType.EVALUATING: self._on_evaluating,
        EventType.WILL_SPEAK: self._on_will_speak,
        EventType.WILL_STAY_SILENT: self._on_will_stay_silent,
        EventType.RESPONSE_START: self._on_response_start,
        EventType.RESPONSE_CHUNK: self._on_response_chunk,
        EventType.RESPONSE_COMPLETE: self._on_response_complete,
        EventType.TOOL_CALL: self._on_tool_call,
        EventType.TOOL_EXECUTING: self._on_tool_executing,
        EventType.TOOL_RESULT: self._on_tool_result,
        EventType.TOOL_PERMISSION_REQUEST: self._on_permission_request,
        EventType.ERROR: self._on_error,
        EventType.TURN_COMPLETE: self._on_turn_complete,
    }
    await handlers[event.type](event)
```

## Technical Approach

### Rich Live Display

Use Rich's `Live` context for real-time updates:

```python
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

class ChatApp:
    def __init__(self):
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="messages", ratio=1),
            Layout(name="status", size=1),
        )

    async def run(self):
        with Live(self.layout, refresh_per_second=10) as live:
            while self.running:
                await self._process_events()
                live.update(self.layout)
```

### Prompt Toolkit Integration

Use prompt_toolkit for advanced input handling:

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory

class InputHandler:
    def __init__(self, models: list[str]):
        mentions = [f"@{m}" for m in models] + ["@all"]
        commands = ["/help", "/quit", "/clear", "/sessions", ...]

        self.completer = WordCompleter(mentions + commands)
        self.session = PromptSession(
            completer=self.completer,
            history=InMemoryHistory(),
            multiline=True,
        )

    async def get_input(self) -> str:
        return await self.session.prompt_async(">>> ")
```

### Streaming Message Updates

Handle streaming chunks efficiently:

```python
class StreamingMessage:
    """Handles real-time message streaming."""

    def __init__(self, model: str, theme: Theme):
        self.model = model
        self.theme = theme
        self.content = ""
        self.is_complete = False

    def append(self, chunk: str) -> None:
        self.content += chunk

    def complete(self, response: ModelResponse) -> None:
        self.content = response.content
        self.is_complete = True
        self.usage = response.usage

    def render(self) -> Panel:
        style = self.theme.model_colors[self.model]
        suffix = "" if self.is_complete else "▌"
        return Panel(
            Markdown(self.content + suffix),
            title=f"[{style}]{self.model.capitalize()}[/{style}]",
            border_style=style,
        )
```

## Theme System

### Default Theme

```python
DEFAULT_THEME = Theme(
    model_colors={
        "claude": "orange3",
        "gpt": "green",
        "gemini": "blue",
        "grok": "purple",
        "user": "white",
        "system": "dim",
    },
    message_styles={
        "user": Style(color="white", bold=True),
        "assistant": Style(color="bright_white"),
        "system": Style(color="dim"),
        "error": Style(color="red", bold=True),
    },
    ui_styles={
        "header": Style(bgcolor="dark_blue"),
        "status": Style(bgcolor="grey23"),
        "border": Style(color="grey50"),
    },
)
```

### Colorblind Theme

```python
COLORBLIND_THEME = Theme(
    model_colors={
        "claude": "bright_yellow",   # High contrast
        "gpt": "bright_cyan",
        "gemini": "bright_magenta",
        "grok": "bright_white",
        "user": "white",
        "system": "dim",
    },
    # ... patterns/shapes for additional distinction
)
```

## CLI Integration

Update `cli.py` to use the new TUI:

```python
async def start_interactive(
    resume: Optional[str] = None,
    verbose: bool = False,
) -> None:
    from codecrew.ui import ChatApp

    settings = get_settings()

    # Create orchestrator with tools
    orchestrator = await create_tool_enabled_orchestrator(
        settings=settings,
        db_path=settings.storage.resolved_database_path,
    )

    # Create and run TUI
    app = ChatApp(
        settings=settings,
        orchestrator=orchestrator,
        resume_session=resume,
    )
    await app.run()
```

## Testing Strategy

### Unit Tests

- Theme loading and color mapping
- Message rendering (Markdown, syntax highlighting)
- Command parsing (/help, /quit, @mentions)
- Event handler mapping

### Integration Tests

- Full event loop with mock orchestrator
- Streaming simulation
- Tool permission flow
- Session lifecycle

### Manual Testing Checklist

- [ ] Streaming displays smoothly
- [ ] @mentions autocomplete correctly
- [ ] All slash commands work
- [ ] Tool calls display properly
- [ ] Permission dialogs function
- [ ] Sessions can be saved/loaded
- [ ] Themes render correctly
- [ ] Keyboard shortcuts respond

## Dependencies

Already available:
- `rich>=13.0.0` - Terminal UI components
- `prompt-toolkit>=3.0.0` - Advanced input handling

No new dependencies required.

## Estimated Test Count

- `test_theme.py`: ~10 tests
- `test_message.py`: ~15 tests
- `test_input.py`: ~12 tests
- `test_commands.py`: ~20 tests
- `test_events.py`: ~14 tests (one per event type)
- `test_dialogs.py`: ~10 tests
- `test_app.py`: ~15 tests (integration)

**Total: ~96 new tests** (Target: 467 total)

## Success Criteria

1. Interactive chat fully functional
2. Real-time streaming displays smoothly
3. All 14 event types handled properly
4. Tool execution visualized with permissions
5. Sessions can be created, loaded, switched
6. All slash commands implemented
7. @mention autocomplete works
8. Theme system supports all 3 themes
9. No regressions in existing 371 tests
10. New tests provide good coverage
