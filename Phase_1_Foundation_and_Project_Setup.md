# Phase 1: Foundation & Project Setup

## Phase Overview
- **Duration Estimate**: 3 days
- **Dependencies**: None - Starting Phase
- **Unlocks**: Phase 2 (Model Clients), Phase 4 (Persistence), Phase 6 (TUI)
- **Risk Level**: Low

## Objectives
1. Establish a fully configured Python project with modern tooling and dependency management
2. Create a functional CLI skeleton that handles basic commands and argument parsing
3. Implement a robust configuration system with YAML support and environment variable fallbacks
4. Design and initialize the SQLite database schema for conversation persistence

## Prerequisites
- [ ] Python 3.11+ installed
- [ ] API keys obtained for at least Claude and GPT (for testing)
- [ ] Git initialized in project directory
- [ ] Development environment set up (virtualenv, IDE configured)

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| `pyproject.toml` | Config | Valid PEP 517 configuration, all dependencies listed |
| CLI entry point | Code | `codecrew --help` displays usage information |
| Configuration system | Code | Loads YAML config, falls back to env vars, validates schema |
| Database schema | Code | SQLite migrations run successfully, tables created |
| Default config file | Config | `~/.codecrew/config.yaml` template with all options |
| Project structure | Code | All directories and `__init__.py` files created |

## Technical Specifications

### Architecture Decisions
1. **Typer over Click**: Typer provides better type hints, automatic help generation, and modern Python syntax while maintaining Click's power
2. **Pydantic Settings**: Use Pydantic for configuration validation, providing type safety and environment variable support out of the box
3. **SQLite with raw queries**: Avoid ORM overhead for simple data model; use migrations for schema management
4. **XDG Base Directory compliance**: Store configs in `~/.codecrew/` for simplicity, but design for future XDG compliance

### Data Models / Schemas

#### SQLite Database Schema
```sql
-- sessions table
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    project_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- messages table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system', 'tool'
    model TEXT,          -- NULL for user messages, model name for assistant
    content TEXT NOT NULL,
    tokens_used INTEGER,
    cost_estimate REAL,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- tool_calls table
CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    parameters JSON,
    result JSON,
    status TEXT,  -- 'success', 'error', 'pending'
    executed_at TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- pinned_context table
CREATE TABLE pinned_context (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Create indexes for common queries
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at);
CREATE INDEX idx_tool_calls_message ON tool_calls(message_id);
```

#### Configuration Schema (Pydantic)
```python
class ModelConfig(BaseModel):
    enabled: bool = True
    model_id: str
    max_tokens: int = 8192
    temperature: float = 0.7

class ConversationConfig(BaseModel):
    first_responder: Literal["rotate", "claude", "gpt", "gemini", "grok"] = "rotate"
    silence_threshold: float = 0.3
    max_context_tokens: int = 100000
    auto_save: bool = True
    save_interval_minutes: int = 5

class UIConfig(BaseModel):
    theme: Literal["default", "minimal", "colorblind"] = "default"
    show_silent_models: bool = True
    show_token_usage: bool = False
    show_cost_estimate: bool = True
    code_theme: str = "monokai"

class ToolsConfig(BaseModel):
    file_write: bool = True
    file_delete: Literal[True, False, "confirm"] = "confirm"
    shell_execute: Literal[True, False, "confirm"] = "confirm"
    git_operations: bool = True

class StorageConfig(BaseModel):
    database_path: str = "~/.codecrew/sessions.db"
    max_sessions: int = 100

class Settings(BaseSettings):
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    
    models: Dict[str, ModelConfig]
    conversation: ConversationConfig
    ui: UIConfig
    tools: ToolsConfig
    storage: StorageConfig
```

### Component Breakdown

#### CLI Entry Point (`codecrew/cli.py`)
- **Purpose**: Main entry point for the application, handles argument parsing and dispatches commands
- **Location**: `codecrew/cli.py`
- **Interfaces**: Called via `python -m codecrew` or `codecrew` command
- **Implementation Notes**: 
  - Use Typer's callback for common options (--config, --verbose)
  - Define subcommands for session management (--resume, --sessions, --search, --export)
  - Default command enters interactive mode

#### Configuration System (`codecrew/config/`)
- **Purpose**: Load, validate, and provide access to configuration settings
- **Location**: `codecrew/config/settings.py`, `codecrew/config/defaults.yaml`
- **Interfaces**: `get_settings()` function returns singleton Settings instance
- **Implementation Notes**:
  - Priority: CLI args > env vars > user config > defaults
  - Create `~/.codecrew/` directory on first run
  - Support `${ENV_VAR}` syntax in YAML values

#### Database Manager (`codecrew/conversation/persistence.py`)
- **Purpose**: Handle all SQLite operations and schema migrations
- **Location**: `codecrew/conversation/persistence.py`
- **Interfaces**: `DatabaseManager` class with async context manager support
- **Implementation Notes**:
  - Use aiosqlite for async operations
  - Implement simple version-based migrations
  - Connection pooling not needed for SQLite

#### Application Bootstrap (`codecrew/__main__.py`)
- **Purpose**: Bootstrap the application, initialize components
- **Location**: `codecrew/__main__.py`
- **Interfaces**: Entry point for `python -m codecrew`
- **Implementation Notes**:
  - Initialize logging first
  - Load configuration
  - Initialize database
  - Hand off to CLI or interactive mode

## Implementation Tasks

### Task Group: Project Scaffolding
- [ ] **[TASK-1.1]** Create project directory structure
  - Files: All directories under `codecrew/`
  - Details: Create all package directories with `__init__.py` files as shown in overview
  - Estimate: 0.5 hours

- [ ] **[TASK-1.2]** Create `pyproject.toml` with dependencies
  - Files: `pyproject.toml`
  - Details: 
    ```toml
    [build-system]
    requires = ["setuptools>=61.0"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "codecrew"
    version = "1.0.0"
    description = "AI Coding Groupchat CLI"
    requires-python = ">=3.11"
    dependencies = [
        "typer>=0.9.0",
        "rich>=13.0.0",
        "prompt-toolkit>=3.0.0",
        "httpx>=0.25.0",
        "aiosqlite>=0.19.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "pyyaml>=6.0",
        "anthropic>=0.18.0",
        "openai>=1.0.0",
        "google-generativeai>=0.4.0",
    ]

    [project.optional-dependencies]
    dev = [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "black>=23.0.0",
        "ruff>=0.1.0",
        "mypy>=1.0.0",
    ]

    [project.scripts]
    codecrew = "codecrew.cli:app"
    ```
  - Estimate: 1 hour

- [ ] **[TASK-1.3]** Set up development environment
  - Files: `.gitignore`, `.python-version`, `requirements-dev.txt`
  - Details: Create virtualenv, install dependencies, configure git hooks
  - Estimate: 0.5 hours

### Task Group: Configuration System
- [ ] **[TASK-1.4]** Implement Pydantic settings models
  - Files: `codecrew/config/settings.py`
  - Details: Define all Pydantic models for configuration with validation
  - Estimate: 2 hours

- [ ] **[TASK-1.5]** Create default configuration YAML
  - Files: `codecrew/config/defaults.yaml`
  - Details: Full default configuration with comments explaining each option
  - Estimate: 1 hour

- [ ] **[TASK-1.6]** Implement config loader with priority system
  - Files: `codecrew/config/__init__.py`
  - Details: 
    - Load defaults, then user config from `~/.codecrew/config.yaml`
    - Override with environment variables (CODECREW_* prefix)
    - Parse `${ENV_VAR}` syntax in YAML strings
    - Create config directory if not exists
  - Estimate: 2 hours

- [ ] **[TASK-1.7]** Add config validation and error messages
  - Files: `codecrew/config/settings.py`
  - Details: Pydantic validators for API keys, paths, and ranges
  - Estimate: 1 hour

### Task Group: Database Setup
- [ ] **[TASK-1.8]** Create database manager class
  - Files: `codecrew/conversation/persistence.py`
  - Details:
    ```python
    class DatabaseManager:
        def __init__(self, db_path: str): ...
        async def initialize(self): ...
        async def execute(self, query: str, params: tuple = ()): ...
        async def fetch_one(self, query: str, params: tuple = ()): ...
        async def fetch_all(self, query: str, params: tuple = ()): ...
        async def close(self): ...
    ```
  - Estimate: 2 hours

- [ ] **[TASK-1.9]** Implement schema migrations
  - Files: `codecrew/conversation/migrations.py`
  - Details: 
    - Store schema version in `schema_version` table
    - Run migrations sequentially from current to latest
    - Initial migration creates all tables
  - Estimate: 1.5 hours

- [ ] **[TASK-1.10]** Create data models for conversation entities
  - Files: `codecrew/conversation/models.py`
  - Details: Pydantic models for Session, Message, ToolCall matching DB schema
  - Estimate: 1 hour

### Task Group: CLI Foundation
- [ ] **[TASK-1.11]** Create main CLI app with Typer
  - Files: `codecrew/cli.py`
  - Details:
    ```python
    import typer
    from rich.console import Console
    
    app = typer.Typer(
        name="codecrew",
        help="AI Coding Groupchat CLI",
        add_completion=True,
    )
    console = Console()
    
    @app.callback(invoke_without_command=True)
    def main(
        ctx: typer.Context,
        resume: Optional[str] = typer.Option(None, help="Resume session"),
        config: Optional[Path] = typer.Option(None, help="Config file path"),
        verbose: bool = typer.Option(False, "-v", "--verbose"),
    ):
        if ctx.invoked_subcommand is None:
            # Enter interactive mode
            start_interactive(resume=resume)
    
    @app.command()
    def sessions(): ...
    
    @app.command()
    def search(query: str): ...
    
    @app.command()
    def export(session_id: str, format: str = "md"): ...
    ```
  - Estimate: 2 hours

- [ ] **[TASK-1.12]** Implement `__main__.py` entry point
  - Files: `codecrew/__main__.py`
  - Details:
    ```python
    import asyncio
    from codecrew.cli import app
    
    def main():
        app()
    
    if __name__ == "__main__":
        main()
    ```
  - Estimate: 0.5 hours

- [ ] **[TASK-1.13]** Create logging configuration
  - Files: `codecrew/utils/logging.py`
  - Details: Configure Rich-based logging handler, log levels, file output
  - Estimate: 1 hour

### Task Group: Initial Testing
- [ ] **[TASK-1.14]** Set up pytest configuration
  - Files: `pytest.ini`, `tests/conftest.py`
  - Details: Configure pytest-asyncio, fixtures for settings and DB
  - Estimate: 1 hour

- [ ] **[TASK-1.15]** Write tests for configuration loading
  - Files: `tests/test_config.py`
  - Details: Test default loading, YAML parsing, env var override, validation
  - Estimate: 1.5 hours

- [ ] **[TASK-1.16]** Write tests for database operations
  - Files: `tests/test_persistence.py`
  - Details: Test migrations, CRUD operations on sessions/messages
  - Estimate: 1.5 hours

## Testing Requirements

### Unit Tests
- [ ] Configuration loads defaults when no file exists
- [ ] Configuration correctly merges user config with defaults
- [ ] Environment variables override config file values
- [ ] Invalid configuration raises appropriate errors
- [ ] Database migrations run successfully on fresh database
- [ ] Database migrations are idempotent (can run multiple times)
- [ ] Session CRUD operations work correctly
- [ ] Message insertion and retrieval maintains order

### Integration Tests
- [ ] CLI `--help` displays all commands and options
- [ ] `codecrew --version` displays correct version
- [ ] Config directory created on first run
- [ ] Database initialized on first run

### Manual Verification
- [ ] Run `pip install -e .` in development mode
- [ ] Execute `codecrew --help` and verify output
- [ ] Check `~/.codecrew/` directory is created with config template
- [ ] Verify database file is created and contains tables
- [ ] Test with various invalid config values and verify error messages

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All tests passing (`pytest tests/`)
- [ ] Code formatted (`black codecrew/`)
- [ ] Linting passes (`ruff check codecrew/`)
- [ ] Type checking passes (`mypy codecrew/`)
- [ ] Documentation updated (README with setup instructions)
- [ ] Git commit with descriptive message
- [ ] Dependencies locked (`pip freeze > requirements.txt`)

## Rollback Plan
This is the foundation phase - if critical issues arise:
1. Delete the `codecrew/` directory
2. Remove entry from `pyproject.toml`
3. Remove database file from `~/.codecrew/`
4. Start fresh with corrected approach

Since no external integrations exist yet, rollback is trivial.

## Notes & Considerations

### Edge Cases
- Config file exists but is invalid YAML
- Database file exists but has incompatible schema
- Missing write permissions for `~/.codecrew/`
- Running on Windows vs Unix (path handling)

### Known Limitations
- Grok/xAI SDK may not be available - plan for mock during development
- No support for multiple profiles/environments in v1

### Future Improvements
- XDG Base Directory compliance for Linux
- Windows AppData support
- Config profiles for different projects
- Database encryption option
