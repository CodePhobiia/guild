# CodeCrew User Guide

Welcome to CodeCrew, an AI coding assistant that creates a group chat environment with multiple AI models collaborating to solve coding problems.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Using the Interface](#using-the-interface)
- [Working with AI Models](#working-with-ai-models)
- [Using Tools](#using-tools)
- [Session Management](#session-management)
- [Commands Reference](#commands-reference)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Tips and Best Practices](#tips-and-best-practices)

## Installation

### From PyPI (Recommended)

```bash
pip install codecrew
```

### From Source

```bash
git clone https://github.com/CodePhobiia/guild.git
cd guild
pip install -e .
```

### Requirements

- Python 3.11 or higher
- Terminal with Unicode support (recommended)

## Quick Start

### 1. Set Up API Keys

CodeCrew supports multiple AI providers. Set up at least one:

```bash
# Claude (Anthropic)
export ANTHROPIC_API_KEY="sk-ant-..."

# GPT (OpenAI)
export OPENAI_API_KEY="sk-..."

# Gemini (Google)
export GOOGLE_API_KEY="AI..."

# Grok (xAI)
export XAI_API_KEY="xai-..."
```

Or create a configuration file at `~/.codecrew/config.yaml`:

```yaml
api_keys:
  anthropic: sk-ant-...
  openai: sk-...
  google: AI...
  xai: xai-...
```

### 2. Launch CodeCrew

```bash
codecrew
```

### 3. Start Chatting

```
You: @claude Help me write a Python function to calculate fibonacci numbers

Claude: I'd be happy to help! Here's an efficient implementation...
```

## Configuration

### Configuration File Location

CodeCrew looks for configuration in:

1. `./codecrew.yaml` (current directory)
2. `~/.codecrew/config.yaml` (home directory)
3. Environment variables

### Configuration Options

```yaml
# API Keys
api_keys:
  anthropic: your-key
  openai: your-key
  google: your-key
  xai: your-key

# Model Settings
models:
  claude:
    model_id: claude-sonnet-4-20250514
    max_tokens: 8192
    temperature: 0.7
  gpt:
    model_id: gpt-4o
    max_tokens: 4096
    temperature: 0.7
  gemini:
    model_id: gemini-2.0-flash
    max_tokens: 8192
    temperature: 0.7

# Conversation Settings
conversation:
  first_responder: rotate  # rotate, claude, gpt, confidence, fixed
  silence_threshold: 0.3   # Minimum confidence to speak
  max_context_tokens: 100000

# Tool Settings
tools:
  enabled: true
  auto_approve_safe: true
  allowed_paths:
    - ./
    - ~/projects

# UI Settings
ui:
  theme: default
  use_unicode: true
  compact_mode: false
```

### Environment Variables

All settings can be overridden with environment variables:

```bash
export CODECREW_CONVERSATION__FIRST_RESPONDER=claude
export CODECREW_TOOLS__ENABLED=true
```

## Using the Interface

### Input Area

- Type your message at the prompt
- Use `Shift+Enter` for multi-line input
- Press `Enter` to send

### Message Display

Messages are displayed with:
- Model name and color coding
- Timestamp
- Token usage (when available)
- Tool calls (if any)

### Status Bar

The bottom of the screen shows:
- Current session name
- Active models
- Token usage
- Pending tool calls

## Working with AI Models

### @Mentions

Direct your message to specific models:

```
@claude Explain this code
@gpt Write unit tests for it
@gemini Review the implementation
@grok Suggest optimizations
@all Everyone, what do you think?
```

### No Mention

Without an @mention, CodeCrew uses the configured `first_responder` strategy:

- **rotate**: Models take turns responding
- **confidence**: Model most confident in helping responds
- **claude/gpt/etc.**: Specific model always responds first

### Model Capabilities

| Model | Best For |
|-------|----------|
| Claude | Complex reasoning, code review, explanations |
| GPT | Code generation, diverse tasks |
| Gemini | Fast responses, multi-modal tasks |
| Grok | Real-time information, casual interactions |

## Using Tools

CodeCrew can interact with your file system and execute commands.

### Available Tools

#### File Tools
- `read_file`: Read file contents
- `write_file`: Create or overwrite files
- `edit_file`: Make targeted edits
- `list_directory`: List directory contents
- `search_files`: Search for files by pattern

#### Shell Tools
- `execute_command`: Run shell commands

#### Git Tools
- `git_status`: Check repository status
- `git_diff`: View changes
- `git_log`: View commit history
- `git_commit`: Create commits
- `git_branch`: Manage branches

### Tool Permissions

Tools have permission levels:

- **SAFE**: Auto-approved (e.g., reading files)
- **CAUTIOUS**: Requires confirmation (e.g., writing files)
- **DANGEROUS**: Always requires approval (e.g., shell commands)
- **BLOCKED**: Cannot be executed (e.g., dangerous commands)

### Tool Examples

```
You: @claude Read the README.md file and summarize it

Claude: I'll read the file for you.
[Tool: read_file] Reading README.md...
[Result: File contents...]

Based on the README, this project is...
```

```
You: @gpt Create a new file called hello.py with a hello world program

GPT: I'll create that file for you.
[Tool: write_file] Creating hello.py...
[Permission Required] Write to hello.py? [Y/n]
```

## Session Management

### Creating Sessions

Sessions are created automatically when you start CodeCrew. Name them:

```
/save my-project-debug
```

### Loading Sessions

```
/load my-project-debug
```

Or use the CLI:

```bash
codecrew sessions  # List all sessions
```

### Exporting Conversations

```
/export json conversation.json
/export markdown conversation.md
```

Or via CLI:

```bash
codecrew export SESSION_ID -f markdown -o output.md
```

## Commands Reference

### Session Commands

| Command | Description |
|---------|-------------|
| `/save [name]` | Save current session |
| `/load <name>` | Load a session |
| `/new [name]` | Start new session |
| `/sessions` | List all sessions |
| `/export <format> <file>` | Export conversation |

### Display Commands

| Command | Description |
|---------|-------------|
| `/clear` | Clear the screen |
| `/compact` | Toggle compact mode |
| `/theme <name>` | Change theme |

### Information Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/models` | Show model status |
| `/config` | Show configuration |
| `/stats` | Show session statistics |

### Conversation Commands

| Command | Description |
|---------|-------------|
| `/pin <message>` | Pin important message |
| `/unpin <id>` | Unpin message |
| `/search <query>` | Search messages |

### Tool Commands

| Command | Description |
|---------|-------------|
| `/tools` | List available tools |
| `/approve <tool>` | Pre-approve a tool |
| `/deny <tool>` | Block a tool |

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `Page Up` | Scroll messages up |
| `Page Down` | Scroll messages down |
| `Home` | Scroll to top |
| `End` | Scroll to bottom |
| `Ctrl+F` | Search messages |

### Editing

| Key | Action |
|-----|--------|
| `Ctrl+A` | Move to line start |
| `Ctrl+E` | Move to line end |
| `Ctrl+U` | Clear line |
| `Ctrl+W` | Delete word |
| `Ctrl+K` | Delete to end of line |

### History

| Key | Action |
|-----|--------|
| `Ctrl+P` / `Up` | Previous history |
| `Ctrl+N` / `Down` | Next history |
| `Ctrl+R` | Search history |

### Display

| Key | Action |
|-----|--------|
| `Ctrl+L` | Clear screen |
| `F1` | Show help |
| `F3` | Toggle compact mode |
| `F5` | Refresh display |

### Session

| Key | Action |
|-----|--------|
| `Ctrl+S` | Save session |
| `Ctrl+O` | Open session picker |

## Tips and Best Practices

### Effective Prompts

1. **Be specific**: Instead of "help with code", say "review this function for edge cases"

2. **Use @mentions strategically**:
   - `@claude` for complex reasoning
   - `@gpt` for quick code generation
   - `@all` for diverse perspectives

3. **Provide context**: Include relevant code snippets and error messages

### Multi-Model Collaboration

1. **Sequential refinement**:
   ```
   @claude Write a sorting algorithm
   @gpt Optimize it for performance
   @gemini Add type hints and documentation
   ```

2. **Parallel review**:
   ```
   @all Review this code for bugs and improvements
   ```

### Tool Usage

1. **Start with read operations**: Let AI understand your codebase first

2. **Review before writing**: Ask AI to explain changes before applying them

3. **Use version control**: Commit before letting AI make changes

### Session Organization

1. **Name sessions descriptively**: `bug-fix-auth-flow`, `feature-user-profile`

2. **Pin important context**: Keep crucial information accessible

3. **Export regularly**: Save important conversations for reference

## Troubleshooting

### API Key Issues

```
Error: API key not configured
```

Solution: Check your environment variables or config file.

### Connection Errors

```
Error: Connection timed out
```

Solution: Check your internet connection and API status.

### Tool Permission Denied

```
Error: Permission denied for tool
```

Solution: Check `allowed_paths` in your configuration.

### High Token Usage

Solution: Use `/clear` to reset context, or configure lower `max_context_tokens`.

## Getting Help

- Run `/help` for in-app help
- Check [GitHub Issues](https://github.com/CodePhobiia/guild/issues)
- Read the [CONTRIBUTING.md](../CONTRIBUTING.md) for development questions
