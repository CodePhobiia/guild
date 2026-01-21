"""Tests for SummaryManager and conversation summarization."""

import uuid
from pathlib import Path
from typing import AsyncIterator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from codecrew.conversation import DatabaseManager, SummaryManager
from codecrew.conversation.summarizer import Summary, SummarizationConfig
from codecrew.models.base import ModelClient
from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    StreamChunk,
    Usage,
)


class MockModelClient(ModelClient):
    """Mock model client for testing."""

    def __init__(self, summary_response: str = "This is a test summary."):
        self._summary_response = summary_response
        self._available = True
        self._tokens_counted = {}
        self._model_id = "mock-model"

    def _default_model_id(self) -> str:
        return "mock-model"

    @property
    def name(self) -> str:
        return "mock"

    @property
    def display_name(self) -> str:
        return "Mock"

    @property
    def color(self) -> str:
        return "white"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_available(self) -> bool:
        return self._available

    async def generate(
        self,
        messages: list[Message],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ModelResponse:
        return ModelResponse(
            content=self._summary_response,
            model=self.name,
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    async def generate_stream(
        self,
        messages: list[Message],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content=self._summary_response, is_complete=True)

    def count_tokens(self, text: str) -> int:
        # Simple approximation: 4 chars per token
        return len(text) // 4


@pytest_asyncio.fixture
async def db_manager(temp_dir: Path) -> DatabaseManager:
    """Create an initialized database manager."""
    db_path = temp_dir / "test_summarizer.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    return db


@pytest_asyncio.fixture
async def summary_manager(db_manager: DatabaseManager) -> SummaryManager:
    """Create a SummaryManager with mock client."""
    client = MockModelClient()
    return SummaryManager(
        db=db_manager,
        summarizer_client=client,
        token_threshold=100,  # Low threshold for testing
        summary_target_tokens=50,
    )


@pytest_asyncio.fixture
async def session_id(db_manager: DatabaseManager) -> str:
    """Create a test session and return its ID."""
    session_id = str(uuid.uuid4())
    await db_manager.create_session(session_id=session_id, name="Summary Test Session")
    return session_id


class TestSummaryManagerInit:
    """Tests for SummaryManager initialization."""

    @pytest.mark.asyncio
    async def test_init_without_client(self, db_manager: DatabaseManager) -> None:
        """Test initializing without a summarizer client."""
        manager = SummaryManager(db=db_manager)
        assert manager.is_enabled is False

    @pytest.mark.asyncio
    async def test_init_with_client(self, db_manager: DatabaseManager) -> None:
        """Test initializing with a summarizer client."""
        client = MockModelClient()
        manager = SummaryManager(db=db_manager, summarizer_client=client)
        assert manager.is_enabled is True

    @pytest.mark.asyncio
    async def test_set_summarizer_client(self, db_manager: DatabaseManager) -> None:
        """Test setting the summarizer client after init."""
        manager = SummaryManager(db=db_manager)
        assert manager.is_enabled is False

        client = MockModelClient()
        manager.set_summarizer_client(client)
        assert manager.is_enabled is True


class TestSummarySaving:
    """Tests for saving and retrieving summaries."""

    @pytest.mark.asyncio
    async def test_save_summary(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test saving a summary."""
        summary = await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="This is a test summary of the conversation.",
            token_count=10,
        )

        assert summary.id is not None
        assert summary.session_id == session_id
        assert summary.summary_type == "incremental"
        assert summary.content == "This is a test summary of the conversation."
        assert summary.token_count == 10

    @pytest.mark.asyncio
    async def test_get_summaries(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test getting all summaries for a session."""
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="Summary 1",
        )
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="Summary 2",
        )
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="full",
            content="Full summary",
        )

        all_summaries = await summary_manager.get_summaries(session_id)
        assert len(all_summaries) == 3

        incremental_only = await summary_manager.get_summaries(
            session_id, summary_type="incremental"
        )
        assert len(incremental_only) == 2

    @pytest.mark.asyncio
    async def test_get_latest_summary(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test getting the latest summary."""
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="First summary",
        )
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="Latest summary",
        )

        latest = await summary_manager.get_latest_summary(session_id)
        assert latest is not None
        assert latest.content == "Latest summary"

    @pytest.mark.asyncio
    async def test_clear_summaries(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test clearing all summaries for a session."""
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="To delete",
        )
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="full",
            content="Also to delete",
        )

        count = await summary_manager.clear_summaries(session_id)
        assert count == 2

        summaries = await summary_manager.get_summaries(session_id)
        assert len(summaries) == 0


class TestAutomaticSummarization:
    """Tests for automatic summarization triggering."""

    @pytest.mark.asyncio
    async def test_check_and_summarize_below_threshold(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test that summarization is not triggered below threshold."""
        # Create messages that are below the token threshold
        messages = [
            Message.user("Hi"),
            Message.assistant("Hello!", model="claude"),
        ]

        token_counter = MockModelClient()
        result = await summary_manager.check_and_summarize(
            session_id=session_id,
            messages=messages,
            token_counter=token_counter,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_check_and_summarize_above_threshold(
        self, db_manager: DatabaseManager, session_id: str
    ) -> None:
        """Test that summarization is triggered above threshold."""
        # Create manager with very low threshold
        client = MockModelClient(summary_response="Generated summary of conversation.")
        manager = SummaryManager(
            db=db_manager,
            summarizer_client=client,
            token_threshold=10,  # Very low threshold
            summary_target_tokens=50,
        )

        # Create enough messages to exceed threshold
        # Need at least 8 messages so split_point (len//2) gives 4+ messages to summarize
        messages = [
            Message.user("This is a longer message that will have more tokens"),
            Message.assistant(
                "This is an equally long response with many tokens",
                model="claude",
            ),
            Message.user("Another message with content"),
            Message.assistant("And another response", model="gpt"),
            Message.user("Fifth message"),
            Message.assistant("Sixth response", model="claude"),
            Message.user("Seventh message here"),
            Message.assistant("Eighth response from model", model="gpt"),
        ]

        result = await manager.check_and_summarize(
            session_id=session_id,
            messages=messages,
            token_counter=client,
        )

        assert result is not None
        assert result.summary_type == "incremental"
        assert result.content == "Generated summary of conversation."

    @pytest.mark.asyncio
    async def test_summarize_disabled_without_client(
        self, db_manager: DatabaseManager, session_id: str
    ) -> None:
        """Test that summarization returns None when disabled."""
        manager = SummaryManager(db=db_manager)  # No client

        messages = [
            Message.user("Test message"),
        ]

        token_counter = MockModelClient()
        result = await manager.check_and_summarize(
            session_id=session_id,
            messages=messages,
            token_counter=token_counter,
        )

        assert result is None


class TestFullConversationSummarization:
    """Tests for full conversation summarization."""

    @pytest.mark.asyncio
    async def test_summarize_full_conversation(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test generating a full conversation summary."""
        messages = [
            Message.user("Hello"),
            Message.assistant("Hi there!", model="claude"),
            Message.user("How are you?"),
            Message.assistant("I'm doing well!", model="claude"),
        ]

        summary = await summary_manager.summarize_full_conversation(
            session_id=session_id,
            messages=messages,
        )

        assert summary is not None
        assert summary.summary_type == "full"
        assert summary.content == "This is a test summary."

    @pytest.mark.asyncio
    async def test_summarize_full_too_few_messages(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test that full summary returns None with too few messages."""
        messages = [
            Message.user("Only one message"),
        ]

        summary = await summary_manager.summarize_full_conversation(
            session_id=session_id,
            messages=messages,
        )

        assert summary is None


class TestCombinedSummaryContext:
    """Tests for combined summary context."""

    @pytest.mark.asyncio
    async def test_get_combined_summary_context(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test getting combined summary context."""
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="First part of conversation covered X and Y.",
        )
        await summary_manager.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content="Second part covered Z and W.",
        )

        context = await summary_manager.get_combined_summary_context(session_id)

        assert context is not None
        assert "[Summary 1]" in context
        assert "[Summary 2]" in context
        assert "First part" in context
        assert "Second part" in context

    @pytest.mark.asyncio
    async def test_get_combined_summary_context_empty(
        self, summary_manager: SummaryManager, session_id: str
    ) -> None:
        """Test getting combined context when no summaries exist."""
        context = await summary_manager.get_combined_summary_context(session_id)
        assert context is None


class TestSummaryModel:
    """Tests for the Summary model."""

    def test_summary_from_db_row(self) -> None:
        """Test creating a Summary from a database row."""
        row = {
            "id": "sum-123",
            "session_id": "sess-456",
            "summary_type": "incremental",
            "content": "Test summary content",
            "message_range_start": "msg-1",
            "message_range_end": "msg-10",
            "token_count": 100,
            "created_at": "2024-01-15T10:30:00",
        }

        summary = Summary.from_db_row(row)

        assert summary.id == "sum-123"
        assert summary.session_id == "sess-456"
        assert summary.summary_type == "incremental"
        assert summary.content == "Test summary content"
        assert summary.message_range_start == "msg-1"
        assert summary.message_range_end == "msg-10"
        assert summary.token_count == 100


class TestSummarizationConfig:
    """Tests for SummarizationConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SummarizationConfig()

        assert config.enabled is True
        assert config.token_threshold == 50000
        assert config.summary_target_tokens == 1000
        assert config.summarize_on_archive is True
        assert config.include_in_context is True

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = SummarizationConfig(
            enabled=False,
            token_threshold=100000,
            summary_target_tokens=2000,
            summarize_on_archive=False,
            include_in_context=False,
        )

        assert config.enabled is False
        assert config.token_threshold == 100000
        assert config.summary_target_tokens == 2000
        assert config.summarize_on_archive is False
        assert config.include_in_context is False
