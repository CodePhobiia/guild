# CodeCrew - AI Assistant Guidelines

## Project Overview

CodeCrew is a CLI-based AI coding assistant that creates a group chat environment with multiple AI models (Claude, GPT, Gemini, Grok) collaborating to solve coding problems. Unlike single-model assistants, CodeCrew enables organic conversations where AI models debate approaches, build on each other's ideas, and collectively solve problems.

## Project Structure

```
codecrew/
├── __init__.py              # Package initialization, version info
├── __main__.py              # Entry point for `python -m codecrew`
├── cli.py                   # Typer CLI commands
├── config/
│   ├── __init__.py          # Config loading, caching, env var expansion
│   ├── settings.py          # Pydantic settings models
│   └── defaults.yaml        # Default configuration values
├── models/
│   ├── __init__.py          # Model registry, factory functions
│   ├── base.py              # ModelClient ABC, retry decorator, errors
│   ├── types.py             # Message, ModelResponse, Usage, etc.
│   ├── tools.py             # ToolDefinition, provider format conversions
│   ├── claude.py            # ClaudeClient (Anthropic SDK)
│   ├── gpt.py               # GPTClient (OpenAI SDK)
│   ├── gemini.py            # GeminiClient (Google SDK)
│   └── grok.py              # GrokClient (xAI via OpenAI-compatible API)
├── orchestrator/
│   ├── __init__.py          # Package exports
│   ├── engine.py            # Main Orchestrator class
│   ├── events.py            # EventType, OrchestratorEvent, SpeakerDecision
│   ├── speaking.py          # SpeakingEvaluator (parallel "should speak?" queries)
│   ├── turns.py             # TurnManager (rotate, confidence, fixed strategies)
│   ├── context.py           # ContextAssembler, ContextSummarizer (token limits, pinning)
│   ├── mentions.py          # @mention parsing (@claude, @gpt, @all, etc.)
│   ├── prompts.py           # Prompt templates for evaluation
│   ├── persistent.py        # PersistentOrchestrator with auto-persistence
│   └── tool_orchestrator.py # ToolEnabledOrchestrator with tool execution loop
├── tools/
│   ├── __init__.py          # Package exports (ToolRegistry, ToolExecutor, etc.)
│   ├── registry.py          # ToolRegistry and Tool classes
│   ├── executor.py          # ToolExecutor with safety guards and timeout
│   ├── permissions.py       # PermissionManager, PermissionLevel enum
│   └── builtin/
│       ├── __init__.py      # Built-in tool registration
│       ├── files.py         # File operation tools (read, write, edit, list, search)
│       └── shell.py         # Shell command execution with safety checks
├── conversation/
│   ├── __init__.py          # Package exports
│   ├── persistence.py       # DatabaseManager (SQLite via aiosqlite)
│   ├── migrations.py        # Schema migrations
│   ├── models.py            # Data models (Session, Message, etc.)
│   ├── manager.py           # ConversationManager (high-level bridge)
│   └── summarizer.py        # SummaryManager (automatic summarization)
└── utils/
    └── logging.py           # Logging configuration

tests/
├── conftest.py              # Pytest fixtures
├── test_config.py           # Config loading tests
├── test_persistence.py      # Database tests
├── test_persistence_batch.py # Batch operations tests
├── test_conversation_manager.py # ConversationManager tests
├── test_summarizer.py       # SummaryManager tests
├── test_models/
│   ├── test_types.py        # Message, Usage, etc. tests
│   ├── test_tools.py        # Tool definition tests
│   └── test_clients.py      # Model client tests
├── test_orchestrator/
│   ├── test_mentions.py     # @mention parsing tests
│   ├── test_turns.py        # Turn management tests
│   ├── test_speaking.py     # Speaking evaluation tests
│   ├── test_context.py      # Context assembly tests
│   ├── test_engine.py       # Integration tests
│   └── test_persistent.py   # PersistentOrchestrator tests
└── test_tools/
    ├── __init__.py          # Test package
    ├── test_registry.py     # ToolRegistry tests
    ├── test_permissions.py  # PermissionManager tests
    ├── test_executor.py     # ToolExecutor tests
    ├── test_builtin.py      # Built-in tools tests
    └── test_tool_orchestrator.py # ToolEnabledOrchestrator tests
```

## Implementation Status

### Completed Phases

**Phase 1: Foundation and Project Setup** ✅
- Project directory structure
- pyproject.toml with dependencies
- Pydantic settings models
- Config loading with priority (CLI > env > config > defaults)
- SQLite database manager with async operations
- Schema migrations
- Typer CLI skeleton
- Logging configuration

**Phase 2: Model Client Abstraction Layer** ✅
- Unified Message, ModelResponse, StreamChunk types
- ToolDefinition with provider format conversions
- ModelClient abstract base class
- ClaudeClient, GPTClient, GeminiClient, GrokClient implementations
- Streaming support for all clients
- Retry logic with exponential backoff
- Mock mode for Grok (development without API key)

**Phase 3: Orchestration Engine** ✅
- OrchestratorEvent types for UI communication
- @mention parsing and routing
- Parallel "should speak?" evaluation
- Turn management (rotate, confidence, fixed)
- Context assembly with token limits
- Main Orchestrator class coordinating full conversation flow

**Phase 4: Conversation & Context Management** ✅
- ConversationManager bridging Orchestrator and DatabaseManager
- PersistentOrchestrator with automatic message persistence
- Session lifecycle management (create, load, switch, archive)
- Bidirectional pin synchronization (memory ↔ database)
- SummaryManager with automatic summarization triggers
- Batch database operations for efficiency
- Conversation statistics and analytics
- Export/import functionality (JSON, Markdown)
- Database migration for summaries table

**Phase 5: Tool System Implementation** ✅
- ToolRegistry for tool discovery and management
- ToolExecutor with timeout protection and safety guards
- Permission system (SAFE, CAUTIOUS, DANGEROUS, BLOCKED levels)
- PermissionManager with session grants and tool overrides
- Built-in file tools (read, write, edit, list_directory, search_files)
- Shell command execution with command safety classification
- Path access restrictions for file operations
- ToolEnabledOrchestrator integrating tools with conversation flow
- Multi-turn tool execution loop with max iteration limits
- Tool argument validation against JSON Schema
- Tool result injection into conversation

### Remaining Phases

- Phase 6: Rich TUI Development
- Phase 7: Commands and User Interaction
- Phase 8: Git Integration
- Phase 9: Polish, Security, Error Handling
- Phase 10: Testing, Documentation, Launch

## Key Design Patterns

### Event-Driven Orchestration
The Orchestrator yields events (`OrchestratorEvent`) that the UI layer consumes:
```python
async for event in orchestrator.process_message("@claude explain this"):
    if event.type == EventType.THINKING:
        show_thinking_indicator()
    elif event.type == EventType.RESPONSE_CHUNK:
        stream_to_ui(event.content)
```

### Parallel Model Evaluation
"Should speak?" queries run concurrently with `asyncio.gather()` to minimize latency.

### Provider-Agnostic Types
`Message`, `ModelResponse`, `ToolCall` work across all providers. Each client handles format conversion internally.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_orchestrator/test_engine.py -v

# Run with coverage
pytest tests/ --cov=codecrew
```

Current: **371 tests passing**

## Dependencies

Core:
- `typer[all]` - CLI framework
- `rich` - Terminal formatting
- `pydantic` + `pydantic-settings` - Configuration
- `aiosqlite` - Async SQLite
- `pyyaml` - YAML config files

AI SDKs:
- `anthropic` - Claude
- `openai` - GPT and Grok (OpenAI-compatible)
- `google-generativeai` - Gemini

## Configuration

API keys can be set via:
1. Environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
2. Config file: `~/.codecrew/config.yaml`

```yaml
api_keys:
  anthropic: sk-ant-...
  openai: sk-...
  google: AI...
  xai: xai-...

conversation:
  first_responder: rotate  # or claude, gpt, confidence, fixed
  silence_threshold: 0.3   # minimum confidence to speak
```

## Common Tasks

### Adding a New Model Provider
1. Create client in `codecrew/models/<provider>.py`
2. Extend `ModelClient` ABC
3. Implement `generate()`, `generate_stream()`, `count_tokens()`
4. Add to `MODEL_CLIENTS` registry in `models/__init__.py`
5. Add to `KNOWN_MODELS` in `orchestrator/mentions.py`
6. Write tests in `tests/test_models/`

### Modifying Speaking Evaluation
- Prompt template: `orchestrator/prompts.py`
- Evaluation logic: `orchestrator/speaking.py`
- Threshold: `config/settings.py` → `ConversationConfig.silence_threshold`

### Adding New Event Types
1. Add to `EventType` enum in `orchestrator/events.py`
2. Add factory method to `OrchestratorEvent`
3. Handle in orchestrator and UI layer

### Using PersistentOrchestrator
The `PersistentOrchestrator` wraps the base orchestrator with automatic persistence:
```python
from codecrew.orchestrator import create_persistent_orchestrator

orchestrator = await create_persistent_orchestrator(
    clients=model_clients,
    settings=settings,
    db_path="~/.codecrew/conversations.db",
    enable_summarization=True,
)

# Create or load a session
session_id = await orchestrator.create_session(name="Debug Session")

# Process messages with automatic persistence
async for event in orchestrator.process_message("@claude help"):
    handle_event(event)

# Get conversation statistics
stats = await orchestrator.get_stats()
```

### Managing Summaries
The `SummaryManager` automatically summarizes when token thresholds are exceeded:
```python
from codecrew.conversation import SummaryManager

summary_manager = SummaryManager(
    db=database_manager,
    summarizer_client=claude_client,
    token_threshold=50000,  # Trigger summarization after 50k tokens
)

# Summaries are generated automatically during conversation
# Or manually generate a full summary:
summary = await summary_manager.summarize_full_conversation(
    session_id=session_id,
    messages=conversation,
)
```

### Using the Tool System
The tool system enables AI models to perform actions like reading files and executing commands:

```python
from codecrew.tools import (
    ToolRegistry,
    ToolExecutor,
    PermissionManager,
    register_builtin_tools,
)
from codecrew.orchestrator import ToolEnabledOrchestrator

# Create tool registry and register built-in tools
registry = ToolRegistry()
register_builtin_tools(registry)

# Create permission manager (auto_approve for development)
permissions = PermissionManager(auto_approve=True)

# Create executor
executor = ToolExecutor(registry=registry, permissions=permissions)

# Create tool-enabled orchestrator
orchestrator = ToolEnabledOrchestrator(
    clients=model_clients,
    settings=settings,
    tool_executor=executor,
    tool_registry=registry,
    max_tool_iterations=10,
)

# Process messages - tools execute automatically
async for event in orchestrator.process_message("Read the README.md file"):
    if event.type == EventType.TOOL_CALL:
        print(f"Tool called: {event.tool_call.name}")
    elif event.type == EventType.TOOL_RESULT:
        print(f"Tool result: {event.tool_result.content[:100]}...")
```

### Adding Custom Tools
```python
from codecrew.tools import create_tool, ToolRegistry
from codecrew.tools.permissions import PermissionLevel
from codecrew.models.tools import ToolDefinition, ToolParameter

# Using the factory function
tool = create_tool(
    name="my_tool",
    description="Does something useful",
    parameters=[
        ToolParameter(name="input", type="string", description="Input value"),
    ],
    handler=lambda args: f"Processed: {args['input']}",
    permission_level=PermissionLevel.SAFE,
)

registry = ToolRegistry()
registry.register(tool)
```

### Permission Levels
- **SAFE**: Auto-approved, no confirmation needed (e.g., read_file)
- **CAUTIOUS**: Requires confirmation by default (e.g., write_file)
- **DANGEROUS**: Always requires explicit approval (e.g., execute_command)
- **BLOCKED**: Completely blocked, cannot be executed (e.g., `rm -rf /`)
