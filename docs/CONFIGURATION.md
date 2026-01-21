# Configuration Reference

This document provides a complete reference for all CodeCrew configuration options.

## Configuration File Locations

CodeCrew searches for configuration files in this order:

1. `./codecrew.yaml` - Current directory
2. `~/.codecrew/config.yaml` - User home directory
3. Environment variables

Later sources override earlier ones. Environment variables have highest priority.

## Complete Configuration Schema

```yaml
# =============================================================================
# API Keys
# =============================================================================
api_keys:
  # Anthropic API key for Claude models
  anthropic: sk-ant-api03-...

  # OpenAI API key for GPT models
  openai: sk-...

  # Google API key for Gemini models
  google: AI...

  # xAI API key for Grok models
  xai: xai-...

# =============================================================================
# Model Configuration
# =============================================================================
models:
  # Claude (Anthropic) settings
  claude:
    # Model ID to use
    # Options: claude-sonnet-4-20250514, claude-3-opus-20240229, etc.
    model_id: claude-sonnet-4-20250514

    # Maximum tokens in response
    max_tokens: 8192

    # Temperature (0.0 = deterministic, 1.0 = creative)
    temperature: 0.7

  # GPT (OpenAI) settings
  gpt:
    model_id: gpt-4o
    max_tokens: 4096
    temperature: 0.7

  # Gemini (Google) settings
  gemini:
    model_id: gemini-2.0-flash
    max_tokens: 8192
    temperature: 0.7

  # Grok (xAI) settings
  grok:
    model_id: grok-beta
    max_tokens: 4096
    temperature: 0.7

# =============================================================================
# Conversation Settings
# =============================================================================
conversation:
  # Strategy for selecting which model responds first
  # Options:
  #   - rotate: Models take turns
  #   - confidence: Model with highest confidence responds
  #   - claude/gpt/gemini/grok: Specific model always first
  #   - fixed: Use fixed order (requires models_order)
  first_responder: rotate

  # Order of models when using 'fixed' strategy
  models_order:
    - claude
    - gpt
    - gemini
    - grok

  # Minimum confidence score to respond (0.0 - 1.0)
  # Models below this threshold stay silent
  silence_threshold: 0.3

  # Maximum tokens to include in context
  max_context_tokens: 100000

  # Enable automatic summarization when context grows large
  enable_summarization: true

  # Token threshold to trigger summarization
  summarization_threshold: 50000

# =============================================================================
# Tool Configuration
# =============================================================================
tools:
  # Enable/disable tool system entirely
  enabled: true

  # Automatically approve SAFE-level tools
  auto_approve_safe: true

  # Paths that tools are allowed to access
  # Empty list = current directory only
  # Use absolute paths or ~ for home directory
  allowed_paths:
    - ./
    - ~/projects

  # Maximum execution time for tools (seconds)
  tool_timeout: 30

  # Maximum iterations for multi-turn tool loops
  max_tool_iterations: 10

  # Tool-specific permission overrides
  # Levels: safe, cautious, dangerous, blocked
  permission_overrides:
    execute_command: dangerous
    write_file: cautious
    read_file: safe

# =============================================================================
# UI Settings
# =============================================================================
ui:
  # Color theme
  # Options: default, dark, light, high_contrast
  theme: default

  # Use Unicode characters (disable for basic terminals)
  use_unicode: true

  # Compact display mode (less whitespace)
  compact_mode: false

  # Show token usage in responses
  show_token_usage: true

  # Show timestamps on messages
  show_timestamps: true

  # Maximum messages to display before scrolling
  max_visible_messages: 100

  # Auto-collapse completed tool calls
  collapse_completed_tools: true

# =============================================================================
# Database Settings
# =============================================================================
database:
  # Path to SQLite database file
  # Use :memory: for in-memory (no persistence)
  path: ~/.codecrew/conversations.db

  # Enable WAL mode for better concurrency
  wal_mode: true

# =============================================================================
# Logging Settings
# =============================================================================
logging:
  # Log level: debug, info, warning, error
  level: info

  # Log file path (null for no file logging)
  file: ~/.codecrew/codecrew.log

  # Maximum log file size in bytes
  max_size: 10485760  # 10 MB

  # Number of backup log files to keep
  backup_count: 3
```

## Environment Variables

All configuration options can be set via environment variables using the pattern:
`CODECREW_<SECTION>__<OPTION>`

### Examples

```bash
# API Keys
export CODECREW_API_KEYS__ANTHROPIC="sk-ant-..."
export CODECREW_API_KEYS__OPENAI="sk-..."

# Conversation settings
export CODECREW_CONVERSATION__FIRST_RESPONDER="claude"
export CODECREW_CONVERSATION__SILENCE_THRESHOLD="0.5"

# Tools
export CODECREW_TOOLS__ENABLED="true"
export CODECREW_TOOLS__AUTO_APPROVE_SAFE="false"

# UI
export CODECREW_UI__THEME="dark"
export CODECREW_UI__COMPACT_MODE="true"
```

### Boolean Values

For boolean options, use:
- True: `true`, `yes`, `1`, `on`
- False: `false`, `no`, `0`, `off`

### List Values

For list options, use JSON format:
```bash
export CODECREW_TOOLS__ALLOWED_PATHS='["./", "~/projects", "/tmp"]'
```

## Model-Specific Configuration

### Claude Models

Available model IDs:
- `claude-sonnet-4-20250514` (recommended)
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

### GPT Models

Available model IDs:
- `gpt-4o` (recommended)
- `gpt-4-turbo`
- `gpt-4`
- `gpt-3.5-turbo`

### Gemini Models

Available model IDs:
- `gemini-2.0-flash` (recommended)
- `gemini-1.5-pro`
- `gemini-1.5-flash`

### Grok Models

Available model IDs:
- `grok-beta`

## Permission Levels

Tool permission levels control how tools are executed:

| Level | Description | User Action |
|-------|-------------|-------------|
| `safe` | Low risk, auto-approved | None required |
| `cautious` | Medium risk | Prompted once per session |
| `dangerous` | High risk | Prompted every time |
| `blocked` | Not allowed | Cannot execute |

### Default Permissions

| Tool | Default Level |
|------|---------------|
| `read_file` | safe |
| `list_directory` | safe |
| `search_files` | safe |
| `write_file` | cautious |
| `edit_file` | cautious |
| `execute_command` | dangerous |
| `git_commit` | cautious |

## Example Configurations

### Minimal Configuration

```yaml
api_keys:
  anthropic: sk-ant-...
```

### Development Setup

```yaml
api_keys:
  anthropic: sk-ant-...
  openai: sk-...

tools:
  enabled: true
  auto_approve_safe: true
  allowed_paths:
    - ./
    - ~/dev

logging:
  level: debug
```

### Production/Secure Setup

```yaml
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}  # Use env var

conversation:
  first_responder: claude
  max_context_tokens: 50000

tools:
  enabled: true
  auto_approve_safe: false
  allowed_paths:
    - ./src
    - ./tests
  permission_overrides:
    execute_command: blocked

logging:
  level: warning
```

### Multi-Model Collaboration

```yaml
api_keys:
  anthropic: sk-ant-...
  openai: sk-...
  google: AI...

conversation:
  first_responder: confidence
  silence_threshold: 0.4

models:
  claude:
    temperature: 0.5  # More focused
  gpt:
    temperature: 0.7  # Balanced
  gemini:
    temperature: 0.8  # More creative
```

## Validation

CodeCrew validates configuration on startup. Invalid configurations will show error messages:

```
Configuration Error: Invalid value for conversation.first_responder: 'invalid'
Valid options: rotate, confidence, claude, gpt, gemini, grok, fixed
```

## Reloading Configuration

Configuration is loaded at startup. To apply changes:

1. Restart CodeCrew, or
2. Use the `/config reload` command (if available)

## Security Considerations

1. **Never commit API keys** to version control
2. Use environment variables for sensitive values
3. Restrict `allowed_paths` to necessary directories
4. Set `execute_command` to `blocked` if not needed
5. Review `permission_overrides` carefully
