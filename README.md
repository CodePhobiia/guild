# CodeCrew

[![CI](https://github.com/CodePhobiia/guild/actions/workflows/ci.yml/badge.svg)](https://github.com/CodePhobiia/guild/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

AI Coding Groupchat CLI - Multiple AI models collaborating in a group chat.

CodeCrew is a CLI-based AI coding assistant that simulates a group chat environment with multiple AI models (Claude, GPT, Gemini, Grok). Unlike traditional single-model coding assistants, CodeCrew enables organic, collaborative conversations where AI models can debate approaches, build on each other's ideas, and collectively solve coding problems.

## Features

- **Multi-Model Chat**: Chat with Claude, GPT, Gemini, and Grok simultaneously
- **@Mentions**: Direct messages to specific models with `@claude`, `@gpt`, `@gemini`, `@grok`, or `@all`
- **Intelligent Speaking**: Models decide when they have something valuable to contribute
- **Tool System**: Built-in tools for file operations, shell commands, and git
- **Session Persistence**: Save, resume, search, and export conversations
- **Rich TUI**: Beautiful terminal interface with syntax highlighting
- **Security First**: Path restrictions, command blocking, permission levels

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/CodePhobiia/guild.git
cd guild

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install
pip install -e .
```

### Set Up API Keys

```bash
# Set at least one API key
export ANTHROPIC_API_KEY="your-key"  # For Claude
export OPENAI_API_KEY="your-key"     # For GPT
export GOOGLE_API_KEY="your-key"     # For Gemini
export XAI_API_KEY="your-key"        # For Grok
```

### Start Chatting

```bash
codecrew
```

```
You: @claude Help me write a Python function to calculate fibonacci numbers

Claude: I'd be happy to help! Here's an efficient implementation using memoization...

You: @gpt Can you optimize that further?

GPT: Great start! Here's an iterative version that uses O(1) space...

You: @all What do you think is the best approach?
```

## Configuration

Create `~/.codecrew/config.yaml`:

```yaml
api_keys:
  anthropic: your-anthropic-key
  openai: your-openai-key
  google: your-google-key
  xai: your-xai-key

conversation:
  first_responder: rotate  # rotate, claude, gpt, confidence
  silence_threshold: 0.3

tools:
  enabled: true
  auto_approve_safe: true
  allowed_paths:
    - ./
    - ~/projects
```

See [Configuration Reference](docs/CONFIGURATION.md) for all options.

## Commands

### CLI Commands

```bash
codecrew                      # Start interactive mode
codecrew --resume last        # Resume last session
codecrew sessions             # List saved sessions
codecrew search "query"       # Search conversation history
codecrew export <id> -f md    # Export session as markdown
codecrew models               # Show model status
```

### In-Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/clear` | Clear screen |
| `/save [name]` | Save session |
| `/load <name>` | Load session |
| `/export <format> <file>` | Export conversation |
| `/models` | Show model status |
| `/tools` | List available tools |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+L` | Clear screen |
| `Ctrl+R` | Search history |
| `Page Up/Down` | Scroll messages |
| `F1` | Show help |

## Tools

CodeCrew can interact with your filesystem and execute commands:

```
You: @claude Read the package.json and tell me what dependencies we have

Claude: I'll read that file for you.
[Tool: read_file] Reading package.json...

Based on the package.json, you have the following dependencies:
- react: ^18.2.0
- typescript: ^5.0.0
...
```

### Available Tools

- **File Tools**: `read_file`, `write_file`, `edit_file`, `list_directory`, `search_files`
- **Shell Tools**: `execute_command` (with safety guards)
- **Git Tools**: `git_status`, `git_diff`, `git_log`, `git_commit`, `git_branch`

### Permission Levels

| Level | Description | Example |
|-------|-------------|---------|
| SAFE | Auto-approved | `read_file` |
| CAUTIOUS | Prompted once | `write_file` |
| DANGEROUS | Always prompted | `execute_command` |
| BLOCKED | Cannot execute | `rm -rf /` |

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=codecrew --cov-report=html

# Run specific tests
pytest tests/test_orchestrator/ -v
```

### Code Quality

```bash
# Format
black codecrew tests

# Lint
ruff check codecrew tests

# Type check
mypy codecrew --ignore-missing-imports
```

## Project Structure

```
codecrew/
├── cli.py               # CLI commands
├── errors.py            # Exception hierarchy
├── config/              # Configuration management
├── models/              # AI model clients (Claude, GPT, Gemini, Grok)
├── orchestrator/        # Conversation orchestration
├── conversation/        # Persistence and session management
├── tools/               # Tool system (file, shell, git)
└── ui/                  # Rich terminal UI

tests/
├── test_models/         # Model client tests
├── test_orchestrator/   # Orchestration tests
├── test_tools/          # Tool system tests
├── test_ui/             # UI component tests
└── e2e/                 # End-to-end tests
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) - Getting started and usage
- [Configuration Reference](docs/CONFIGURATION.md) - All configuration options
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Contributing](CONTRIBUTING.md) - Development guidelines
- [Changelog](CHANGELOG.md) - Version history

## Requirements

- Python 3.11 or higher
- Terminal with Unicode support (recommended)
- API key for at least one AI provider

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) - Claude
- [OpenAI SDK](https://github.com/openai/openai-python) - GPT
- [Google Generative AI](https://github.com/google/generative-ai-python) - Gemini
