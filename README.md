# CodeCrew

AI Coding Groupchat CLI - Multiple AI models collaborating in a group chat.

CodeCrew is a CLI-based AI coding assistant that simulates a group chat environment with multiple AI models (Claude, GPT, Gemini, Grok). Unlike traditional single-model coding assistants, CodeCrew enables organic, collaborative conversations where AI models can debate approaches, build on each other's ideas, and collectively solve coding problems.

## Features

- **Multi-Model Chat**: Chat with Claude, GPT, Gemini, and Grok simultaneously
- **@Mentions**: Direct messages to specific models with `@claude`, `@gpt`, `@gemini`, `@grok`, or `@all`
- **Intelligent Speaking**: Models decide when they have something valuable to contribute
- **Session Persistence**: Save, resume, search, and export conversations
- **File Operations**: Read, write, edit, and search files
- **Git Integration**: Git operations with AI assistance
- **Rich TUI**: Beautiful terminal interface with syntax highlighting

## Installation

### Requirements

- Python 3.11 or higher
- API keys for at least one provider (Anthropic, OpenAI, Google, or xAI)

### Install from source

```bash
# Clone the repository
git clone https://github.com/CodePhobiia/guild.git
cd guild

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

## Configuration

### API Keys

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export GOOGLE_API_KEY="your-google-key"
export XAI_API_KEY="your-xai-key"
```

Or configure them in `~/.codecrew/config.yaml`:

```yaml
api_keys:
  anthropic: your-anthropic-key
  openai: your-openai-key
  google: your-google-key
  xai: your-xai-key
```

### Configuration File

A default configuration file will be created at `~/.codecrew/config.yaml` on first run. See `codecrew/config/defaults.yaml` for all available options.

## Usage

### Start Interactive Mode

```bash
codecrew
```

### Commands

```bash
codecrew --help          # Show help
codecrew --version       # Show version
codecrew sessions        # List saved sessions
codecrew search "query"  # Search conversation history
codecrew export <id>     # Export a session
codecrew config          # Show current configuration
codecrew models          # Show model status
```

### Resume a Session

```bash
codecrew --resume last           # Resume last session
codecrew --resume <session-id>   # Resume specific session
```

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black codecrew/

# Lint
ruff check codecrew/

# Type check
mypy codecrew/
```

## Project Structure

```
codecrew/
├── __init__.py
├── __main__.py          # Entry point
├── cli.py               # CLI commands
├── config/              # Configuration management
├── models/              # AI model clients
├── orchestrator/        # Conversation orchestration
├── conversation/        # Persistence and data models
├── tools/               # Tool implementations
├── ui/                  # Terminal UI
├── commands/            # Chat commands
└── utils/               # Utilities
```

## License

MIT
