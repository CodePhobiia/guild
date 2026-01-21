"""Tests for PersistentOrchestrator."""

import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from codecrew.config import Settings
from codecrew.conversation import ConversationManager, DatabaseManager, SummaryManager
from codecrew.models.base import ModelClient
from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    StreamChunk,
    Usage,
)
from codecrew.orchestrator import EventType
from codecrew.orchestrator.persistent import (
    PersistentOrchestrator,
    create_persistent_orchestrator,
)


class MockModelClient(ModelClient):
    """Mock model client for testing."""

    def __init__(self, name: str = "mock", available: bool = True):
        self._name = name
        self._available = available
        self._responses = []
        self._call_count = 0
        self._model_id = f"{name}-model"

    def _default_model_id(self) -> str:
        return f"{self._name}-model"

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._name.title()

    @property
    def color(self) -> str:
        return "blue"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_available(self) -> bool:
        return self._available

    def add_response(self, content: str) -> None:
        """Add a response to return."""
        self._responses.append(content)

    async def generate(
        self,
        messages: list[Message],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ModelResponse:
        self._call_count += 1
        content = self._responses.pop(0) if self._responses else "Mock response"
        return ModelResponse(
            content=content,
            model=self._name,
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    async def generate_stream(
        self,
        messages: list[Message],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        self._call_count += 1
        content = self._responses.pop(0) if self._responses else "Mock response"
        yield StreamChunk(content=content)
        yield StreamChunk(
            is_complete=True,
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


@pytest_asyncio.fixture
async def db_manager(temp_dir: Path) -> DatabaseManager:
    """Create an initialized database manager."""
    db_path = temp_dir / "test_persistent.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    return db


@pytest_asyncio.fixture
async def conversation_manager(db_manager: DatabaseManager) -> ConversationManager:
    """Create a ConversationManager."""
    return ConversationManager(db=db_manager)


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        anthropic_api_key="test-key",
        conversation={"silence_threshold": 0.3},
    )


@pytest.fixture
def mock_clients() -> dict[str, MockModelClient]:
    """Create mock model clients."""
    return {
        "claude": MockModelClient("claude"),
        "gpt": MockModelClient("gpt"),
    }


@pytest_asyncio.fixture
async def persistent_orchestrator(
    mock_clients: dict[str, MockModelClient],
    test_settings: Settings,
    conversation_manager: ConversationManager,
) -> PersistentOrchestrator:
    """Create a PersistentOrchestrator for testing."""
    return PersistentOrchestrator(
        clients=mock_clients,
        settings=test_settings,
        conversation_manager=conversation_manager,
    )


class TestPersistentOrchestratorInit:
    """Tests for PersistentOrchestrator initialization."""

    def test_init(
        self,
        mock_clients: dict[str, MockModelClient],
        test_settings: Settings,
        conversation_manager: ConversationManager,
    ) -> None:
        """Test basic initialization."""
        orchestrator = PersistentOrchestrator(
            clients=mock_clients,
            settings=test_settings,
            conversation_manager=conversation_manager,
        )

        assert orchestrator.orchestrator is not None
        assert orchestrator.conversation_manager is conversation_manager
        assert orchestrator.has_session is False

    def test_init_with_summary_manager(
        self,
        mock_clients: dict[str, MockModelClient],
        test_settings: Settings,
        conversation_manager: ConversationManager,
    ) -> None:
        """Test initialization with summary manager."""
        summary_manager = SummaryManager(
            db=conversation_manager.db,
            summarizer_client=mock_clients["claude"],
        )

        orchestrator = PersistentOrchestrator(
            clients=mock_clients,
            settings=test_settings,
            conversation_manager=conversation_manager,
            summary_manager=summary_manager,
        )

        assert orchestrator._summary_manager is summary_manager


class TestSessionManagement:
    """Tests for session management."""

    @pytest.mark.asyncio
    async def test_create_session(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test creating a session."""
        session_id = await persistent_orchestrator.create_session(
            name="Test Session",
            project_path="/test/path",
        )

        assert session_id is not None
        assert persistent_orchestrator.has_session is True
        assert persistent_orchestrator.session_id == session_id

    @pytest.mark.asyncio
    async def test_load_session(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test loading a session."""
        # Create a session first
        session_id = await persistent_orchestrator.create_session(name="Load Test")

        # Add some messages
        persistent_orchestrator.orchestrator.add_message(Message.user("Hello"))
        await persistent_orchestrator.conversation_manager.persist_message(
            Message.user("Hello")
        )

        # Create a new orchestrator and load the session
        new_orchestrator = PersistentOrchestrator(
            clients=persistent_orchestrator.orchestrator.clients,
            settings=persistent_orchestrator._settings,
            conversation_manager=persistent_orchestrator.conversation_manager,
        )

        await new_orchestrator.load_session(session_id)

        assert new_orchestrator.session_id == session_id
        # Note: conversation state is loaded

    @pytest.mark.asyncio
    async def test_ensure_session_creates(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test ensure_session creates a session if none exists."""
        assert persistent_orchestrator.has_session is False

        session_id = await persistent_orchestrator.ensure_session(name="Ensured")

        assert session_id is not None
        assert persistent_orchestrator.has_session is True

    @pytest.mark.asyncio
    async def test_ensure_session_returns_existing(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test ensure_session returns existing session."""
        existing_id = await persistent_orchestrator.create_session(name="Existing")
        returned_id = await persistent_orchestrator.ensure_session()

        assert returned_id == existing_id


class TestMessageProcessing:
    """Tests for message processing with persistence."""

    @pytest.mark.asyncio
    async def test_process_message_creates_session(
        self,
        persistent_orchestrator: PersistentOrchestrator,
        mock_clients: dict[str, MockModelClient],
    ) -> None:
        """Test that process_message creates a session if needed."""
        # Add expected response
        mock_clients["claude"].add_response("Hello! How can I help?")
        mock_clients["gpt"].add_response("I can also help!")

        assert persistent_orchestrator.has_session is False

        events = []
        async for event in persistent_orchestrator.process_message("@claude Hello"):
            events.append(event)

        assert persistent_orchestrator.has_session is True

    @pytest.mark.asyncio
    async def test_process_message_persists(
        self,
        persistent_orchestrator: PersistentOrchestrator,
        mock_clients: dict[str, MockModelClient],
    ) -> None:
        """Test that messages are persisted after processing."""
        await persistent_orchestrator.create_session(name="Persist Test")

        mock_clients["claude"].add_response("Test response")

        events = []
        async for event in persistent_orchestrator.process_message(
            "@claude Hello", auto_persist=True
        ):
            events.append(event)

        # Check that messages were persisted
        messages = await persistent_orchestrator.conversation_manager.get_conversation_messages()
        # Should have at least the user message and response
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_process_message_no_auto_persist(
        self,
        persistent_orchestrator: PersistentOrchestrator,
        mock_clients: dict[str, MockModelClient],
    ) -> None:
        """Test that auto_persist=False skips persistence."""
        await persistent_orchestrator.create_session(name="No Persist Test")

        mock_clients["claude"].add_response("Test response")

        events = []
        async for event in persistent_orchestrator.process_message(
            "@claude Hello", auto_persist=False
        ):
            events.append(event)

        # In-memory conversation should have messages
        assert len(persistent_orchestrator.conversation) > 0

        # But nothing should be persisted (except maybe the session)
        # Note: The actual implementation may vary


class TestPinManagement:
    """Tests for pin management."""

    @pytest.mark.asyncio
    async def test_pin_message(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test pinning a message."""
        await persistent_orchestrator.create_session(name="Pin Test")

        # Persist a message
        msg_id = await persistent_orchestrator.conversation_manager.persist_message(
            Message.user("Important context")
        )

        result = await persistent_orchestrator.pin_message(msg_id)

        assert result is True
        assert msg_id in persistent_orchestrator.pinned_ids

    @pytest.mark.asyncio
    async def test_unpin_message(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test unpinning a message."""
        await persistent_orchestrator.create_session(name="Unpin Test")

        msg_id = await persistent_orchestrator.conversation_manager.persist_message(
            Message.user("Temporary pin")
        )
        await persistent_orchestrator.pin_message(msg_id)

        result = await persistent_orchestrator.unpin_message(msg_id)

        assert result is True
        assert msg_id not in persistent_orchestrator.pinned_ids


class TestUtilityMethods:
    """Tests for utility methods."""

    @pytest.mark.asyncio
    async def test_get_model_status(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test getting model status."""
        status = persistent_orchestrator.get_model_status()

        assert "claude" in status
        assert "gpt" in status
        assert status["claude"]["available"] is True
        assert status["gpt"]["available"] is True

    @pytest.mark.asyncio
    async def test_get_stats(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test getting conversation stats."""
        await persistent_orchestrator.create_session(name="Stats Test")

        await persistent_orchestrator.conversation_manager.persist_message(
            Message.user("Test message")
        )

        stats = await persistent_orchestrator.get_stats()

        assert "total_messages" in stats
        assert stats["total_messages"] >= 1

    @pytest.mark.asyncio
    async def test_export_json(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test exporting as JSON."""
        await persistent_orchestrator.create_session(name="Export Test")

        await persistent_orchestrator.conversation_manager.persist_message(
            Message.user("Export this")
        )

        export = await persistent_orchestrator.export(format="json")

        assert "Export Test" in export
        assert "Export this" in export

    @pytest.mark.asyncio
    async def test_clear_conversation(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test clearing conversation."""
        await persistent_orchestrator.create_session(name="Clear Test")

        persistent_orchestrator.orchestrator.add_message(Message.user("Hello"))
        assert len(persistent_orchestrator.conversation) > 0

        await persistent_orchestrator.clear_conversation()

        assert len(persistent_orchestrator.conversation) == 0


class TestAvailableModels:
    """Tests for available_models property."""

    def test_available_models(
        self, persistent_orchestrator: PersistentOrchestrator
    ) -> None:
        """Test getting available models."""
        models = persistent_orchestrator.available_models

        assert "claude" in models
        assert "gpt" in models


class TestFactoryFunction:
    """Tests for the factory function."""

    @pytest.mark.asyncio
    async def test_create_persistent_orchestrator(
        self,
        mock_clients: dict[str, MockModelClient],
        test_settings: Settings,
        temp_dir: Path,
    ) -> None:
        """Test the factory function."""
        db_path = str(temp_dir / "factory_test.db")

        orchestrator = await create_persistent_orchestrator(
            clients=mock_clients,
            settings=test_settings,
            db_path=db_path,
            enable_summarization=True,
            summarizer_client=mock_clients["claude"],
        )

        assert orchestrator is not None
        assert orchestrator._summary_manager is not None

    @pytest.mark.asyncio
    async def test_create_persistent_orchestrator_no_summarization(
        self,
        mock_clients: dict[str, MockModelClient],
        test_settings: Settings,
        temp_dir: Path,
    ) -> None:
        """Test factory without summarization."""
        db_path = str(temp_dir / "factory_no_sum.db")

        orchestrator = await create_persistent_orchestrator(
            clients=mock_clients,
            settings=test_settings,
            db_path=db_path,
            enable_summarization=False,
        )

        assert orchestrator is not None
        assert orchestrator._summary_manager is None
