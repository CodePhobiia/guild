# Changelog

All notable changes to CodeCrew will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-01-21

### Added

#### Phase 1: Foundation and Project Setup
- Project directory structure with modular architecture
- Pydantic settings models for type-safe configuration
- Config loading with priority (CLI > environment > config file > defaults)
- SQLite database manager with async operations via aiosqlite
- Schema migrations system
- Typer CLI skeleton with commands
- Comprehensive logging configuration

#### Phase 2: Model Client Abstraction Layer
- Unified `Message`, `ModelResponse`, `StreamChunk` types
- `ToolDefinition` with provider format conversions
- `ModelClient` abstract base class
- `ClaudeClient` (Anthropic SDK integration)
- `GPTClient` (OpenAI SDK integration)
- `GeminiClient` (Google Generative AI SDK integration)
- `GrokClient` (xAI via OpenAI-compatible API)
- Streaming support for all model clients
- Retry logic with exponential backoff
- Mock mode for development without API keys

#### Phase 3: Orchestration Engine
- `OrchestratorEvent` types for UI communication
- @mention parsing and routing (@claude, @gpt, @gemini, @grok, @all)
- Parallel "should speak?" evaluation
- Turn management strategies (rotate, confidence, fixed)
- Context assembly with token limits
- Main `Orchestrator` class coordinating full conversation flow

#### Phase 4: Conversation & Context Management
- `ConversationManager` bridging Orchestrator and DatabaseManager
- `PersistentOrchestrator` with automatic message persistence
- Session lifecycle management (create, load, switch, archive)
- Bidirectional pin synchronization (memory ↔ database)
- `SummaryManager` with automatic summarization triggers
- Batch database operations for efficiency
- Conversation statistics and analytics
- Export/import functionality (JSON, Markdown)

#### Phase 5: Tool System Implementation
- `ToolRegistry` for tool discovery and management
- `ToolExecutor` with timeout protection and safety guards
- Permission system (SAFE, CAUTIOUS, DANGEROUS, BLOCKED levels)
- `PermissionManager` with session grants and tool overrides
- Built-in file tools (read, write, edit, list_directory, search_files)
- Shell command execution with safety classification
- Path access restrictions for file operations
- `ToolEnabledOrchestrator` integrating tools with conversation flow
- Multi-turn tool execution loop with iteration limits
- Tool argument validation against JSON Schema

#### Phase 6: Rich TUI Development
- Rich-based terminal UI with responsive layout
- Model response panels with syntax highlighting
- Tool execution visualization with status indicators
- Real-time streaming display
- Theme system with customizable colors
- Unicode/ASCII fallback for terminal compatibility
- Keyboard shortcuts system
- Scroll navigation for message history

#### Phase 7: Commands and User Interaction
- Slash commands (/help, /clear, /save, /load, /export, etc.)
- Session management commands
- Configuration commands
- Input history with persistence
- Clipboard integration
- Multi-line input support
- Command autocomplete

#### Phase 8: Git Integration
- Git repository detection and management
- Built-in git tools (status, diff, log, commit, branch operations)
- Safe git command execution
- Repository context in conversations

#### Phase 9: Security, Error Handling, Polish
- Centralized exception hierarchy (`codecrew/errors.py`)
- Path traversal protection using `Path.relative_to()`
- Shell injection prevention with blocked command patterns
- Blocked paths for sensitive system files
- Improved error handling with specific exception types
- Comprehensive logging throughout codebase
- 62 security tests

#### Phase 10: Testing, Documentation, Launch
- GitHub Actions CI/CD pipeline
- Multi-platform testing (Ubuntu, Windows, macOS)
- Python 3.11, 3.12 test matrix
- Code coverage reporting with pytest-cov
- CONTRIBUTING.md guide
- User documentation
- E2E integration tests
- Release automation workflow

### Tests
- 800+ tests covering all major components
- Unit tests for models, orchestrator, tools, UI
- Integration tests for conversation flows
- Security tests for path traversal and injection prevention

## [0.1.0] - Initial Development

### Added
- Initial project scaffolding
- Basic CLI structure
- Configuration system prototype

---

[Unreleased]: https://github.com/CodePhobiia/guild/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/CodePhobiia/guild/releases/tag/v1.0.0
[0.1.0]: https://github.com/CodePhobiia/guild/releases/tag/v0.1.0
