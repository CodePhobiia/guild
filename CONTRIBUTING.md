# Contributing to CodeCrew

Thank you for your interest in contributing to CodeCrew! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment
4. Create a branch for your changes
5. Make your changes and test them
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A terminal with Unicode support (recommended)

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/guild.git
cd guild

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### API Keys (Optional)

For testing with real AI models, you'll need API keys:

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
export XAI_API_KEY="your-key"
```

Most tests use mocks and don't require API keys.

## Project Structure

```
codecrew/
├── __init__.py           # Package initialization
├── cli.py                # CLI commands (Typer)
├── errors.py             # Centralized exception hierarchy
├── config/               # Configuration management
├── models/               # AI model clients
├── orchestrator/         # Conversation orchestration
├── tools/                # Tool system (file, shell, git)
├── conversation/         # Persistence and session management
├── ui/                   # Rich TUI components
└── utils/                # Utility functions

tests/
├── conftest.py           # Pytest fixtures
├── test_models/          # Model client tests
├── test_orchestrator/    # Orchestration tests
├── test_tools/           # Tool system tests
├── test_ui/              # UI component tests
└── e2e/                  # End-to-end tests
```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-new-model` - New features
- `fix/tool-execution-error` - Bug fixes
- `docs/update-readme` - Documentation
- `refactor/simplify-orchestrator` - Code refactoring

### Commit Messages

Follow conventional commits:
- `feat: Add support for new AI model`
- `fix: Handle timeout in tool execution`
- `docs: Update installation guide`
- `test: Add tests for context assembly`
- `refactor: Simplify message conversion`

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_orchestrator/test_engine.py

# Run tests matching a pattern
pytest -k "test_mention"

# Run with coverage
pytest --cov=codecrew --cov-report=html
```

### Writing Tests

- Place tests in the appropriate `tests/` subdirectory
- Use descriptive test names: `test_should_parse_multiple_mentions`
- Use pytest fixtures from `conftest.py`
- Mock external services (AI APIs, file system)

Example test:

```python
import pytest
from codecrew.orchestrator.mentions import parse_mentions

def test_should_parse_single_mention():
    """Test parsing a single @mention."""
    result = parse_mentions("@claude help me")
    assert result.mentioned_models == ["claude"]
    assert result.cleaned_message == "help me"

@pytest.mark.asyncio
async def test_should_generate_response(mock_client):
    """Test response generation with mock client."""
    response = await mock_client.generate(messages)
    assert response.content is not None
```

### Test Categories

- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test component interactions
- **E2E tests**: Test full conversation workflows

## Code Style

### Formatting

We use [Black](https://black.readthedocs.io/) for code formatting:

```bash
# Format code
black codecrew tests

# Check formatting
black --check codecrew tests
```

### Linting

We use [Ruff](https://docs.astral.sh/ruff/) for linting:

```bash
# Run linter
ruff check codecrew tests

# Fix auto-fixable issues
ruff check --fix codecrew tests
```

### Type Checking

We use [mypy](https://mypy.readthedocs.io/) for static type checking:

```bash
mypy codecrew --ignore-missing-imports
```

### Code Guidelines

- Use type hints for all function parameters and return values
- Write docstrings for public functions and classes
- Keep functions focused and under 50 lines when possible
- Use meaningful variable names
- Handle errors gracefully with appropriate exception types

Example:

```python
from codecrew.errors import InputValidationError

def process_message(message: str, max_length: int = 1000) -> str:
    """Process a user message.

    Args:
        message: The message to process
        max_length: Maximum allowed message length

    Returns:
        The processed message

    Raises:
        InputValidationError: If message exceeds max_length
    """
    if len(message) > max_length:
        raise InputValidationError(
            f"Message exceeds maximum length of {max_length}",
            field="message",
            value=message[:50] + "...",
        )
    return message.strip()
```

## Submitting Changes

### Before Submitting

1. Run all tests: `pytest`
2. Check formatting: `black --check codecrew tests`
3. Run linter: `ruff check codecrew tests`
4. Run type checker: `mypy codecrew --ignore-missing-imports`

### Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all checks pass
4. Fill out the PR template completely
5. Request review from maintainers

### PR Guidelines

- Keep PRs focused on a single change
- Include tests for new code
- Update CHANGELOG.md for user-facing changes
- Reference related issues in the description

## Adding New Features

### Adding a New AI Model

1. Create client in `codecrew/models/<provider>.py`
2. Extend `ModelClient` ABC
3. Implement `generate()`, `generate_stream()`, `count_tokens()`
4. Add to `MODEL_CLIENTS` in `models/__init__.py`
5. Add to `KNOWN_MODELS` in `orchestrator/mentions.py`
6. Write tests in `tests/test_models/`

### Adding a New Tool

1. Create tool in `codecrew/tools/builtin/<tool>.py`
2. Define parameters using `ToolParameter`
3. Implement handler function
4. Set appropriate permission level
5. Register in `tools/builtin/__init__.py`
6. Write tests in `tests/test_tools/`

### Adding a New CLI Command

1. Add command in `codecrew/cli.py`
2. Use Typer decorators and type hints
3. Add help text and examples
4. Write tests for the command

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing issues before creating new ones

Thank you for contributing!
