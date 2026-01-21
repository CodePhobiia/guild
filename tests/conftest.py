"""Pytest configuration and fixtures for CodeCrew tests."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

from codecrew.config import Settings, reset_settings
from codecrew.conversation import DatabaseManager


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """Create a temporary config file."""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(
        """
api_keys:
  anthropic: test-anthropic-key
  openai: test-openai-key

models:
  claude:
    enabled: true
    model_id: claude-sonnet-4-20250514
  gpt:
    enabled: true
    model_id: gpt-4o
  gemini:
    enabled: false
    model_id: gemini-2.0-flash
  grok:
    enabled: false
    model_id: grok-3

conversation:
  first_responder: claude
  silence_threshold: 0.5

storage:
  database_path: "{db_path}"
""".format(db_path=str(temp_dir / "test.db").replace("\\", "/"))
    )
    return config_path


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary paths."""
    reset_settings()
    return Settings(
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key",
        storage={"database_path": str(temp_dir / "test.db")},
    )


@pytest_asyncio.fixture
async def db_manager(temp_dir: Path) -> AsyncGenerator[DatabaseManager, None]:
    """Create an initialized database manager for tests."""
    db_path = temp_dir / "test.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    yield db


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables for testing."""
    # Store original values
    original = {}
    env_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
        "CODECREW_ANTHROPIC_API_KEY",
        "CODECREW_OPENAI_API_KEY",
    ]
    for var in env_vars:
        original[var] = os.environ.pop(var, None)

    reset_settings()

    yield

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]

    reset_settings()


@pytest.fixture
def mock_api_keys(clean_env: None) -> Generator[None, None, None]:
    """Set mock API keys for testing."""
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    yield
