"""Integration tests for the orchestrator engine."""

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from codecrew.config import Settings
from codecrew.models.types import (
    FinishReason,
    Message,
    ModelResponse,
    StreamChunk,
    Usage,
)
from codecrew.orchestrator import Orchestrator, EventType, OrchestratorEvent


class MockModelClient:
    """Mock model client for integration tests."""

    def __init__(
        self,
        name: str,
        response_content: str = "Test response",
        should_speak_response: str = '{"should_speak": true, "confidence": 0.8, "reason": "test"}',
        is_available: bool = True,
    ):
        self.name = name
        self.display_name = name.title()
        self.color = "#000000"
        self.model_id = f"{name}-test"
        self._response_content = response_content
        self._should_speak_response = should_speak_response
        self._is_available = is_available
        self._call_count = 0

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def generate(
        self,
        messages,
        max_tokens=None,
        temperature=None,
        system=None,
        tools=None,
    ) -> ModelResponse:
        self._call_count += 1
        # First call is usually should_speak evaluation (short max_tokens)
        if max_tokens and max_tokens <= 150:
            content = self._should_speak_response
        else:
            content = self._response_content

        return ModelResponse(
            content=content,
            model=self.name,
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    async def generate_stream(
        self,
        messages,
        max_tokens=None,
        temperature=None,
        system=None,
        tools=None,
    ) -> AsyncIterator[StreamChunk]:
        # Yield content in chunks
        for char in self._response_content:
            yield StreamChunk(content=char)

        yield StreamChunk(
            is_complete=True,
            finish_reason=FinishReason.STOP,
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


def create_test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        anthropic_api_key="test-key",
        openai_api_key="test-key",
        google_api_key="test-key",
    )


class TestOrchestrator:
    """Tests for Orchestrator class."""

    @pytest.mark.asyncio
    async def test_basic_message_processing(self) -> None:
        """Test processing a simple message."""
        clients = {
            "claude": MockModelClient("claude", response_content="Hello from Claude!"),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("Hello"):
            events.append(event)

        # Check event sequence
        event_types = [e.type for e in events]

        assert EventType.THINKING in event_types
        assert EventType.WILL_SPEAK in event_types or EventType.WILL_STAY_SILENT in event_types
        assert EventType.TURN_COMPLETE in event_types

    @pytest.mark.asyncio
    async def test_mention_parsing(self) -> None:
        """Test that @mentions are parsed correctly."""
        clients = {
            "claude": MockModelClient("claude"),
            "gpt": MockModelClient(
                "gpt",
                should_speak_response='{"should_speak": false, "confidence": 0.2, "reason": "not mentioned"}',
            ),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("@claude what do you think?"):
            events.append(event)

        # Claude should be forced to speak
        will_speak_events = [e for e in events if e.type == EventType.WILL_SPEAK]
        assert any(e.decision.is_forced for e in will_speak_events)

    @pytest.mark.asyncio
    async def test_conversation_history_grows(self) -> None:
        """Test that conversation history grows with each turn."""
        clients = {
            "claude": MockModelClient("claude"),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        # Process first message
        async for _ in orchestrator.process_message("First message"):
            pass

        initial_len = len(orchestrator.conversation)
        assert initial_len >= 1  # At least user message

        # Process second message
        async for _ in orchestrator.process_message("Second message"):
            pass

        # Should have grown
        assert len(orchestrator.conversation) > initial_len

    @pytest.mark.asyncio
    async def test_multiple_models_respond(self) -> None:
        """Test multiple models responding to a message."""
        clients = {
            "claude": MockModelClient("claude", response_content="Claude says hi"),
            "gpt": MockModelClient("gpt", response_content="GPT says hello"),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("@all hello everyone"):
            events.append(event)

        # Should have responses from both models
        response_events = [e for e in events if e.type == EventType.RESPONSE_COMPLETE]
        assert len(response_events) == 2

        responding_models = {e.model for e in response_events}
        assert responding_models == {"claude", "gpt"}

    @pytest.mark.asyncio
    async def test_all_silent(self) -> None:
        """Test when all models decide to stay silent."""
        clients = {
            "claude": MockModelClient(
                "claude",
                should_speak_response='{"should_speak": false, "confidence": 0.1, "reason": "nothing to add"}',
            ),
            "gpt": MockModelClient(
                "gpt",
                should_speak_response='{"should_speak": false, "confidence": 0.1, "reason": "covered"}',
            ),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("test"):
            events.append(event)

        # Should have WILL_STAY_SILENT events and no RESPONSE_COMPLETE
        response_events = [e for e in events if e.type == EventType.RESPONSE_COMPLETE]
        assert len(response_events) == 0

        silent_events = [e for e in events if e.type == EventType.WILL_STAY_SILENT]
        assert len(silent_events) == 2

    @pytest.mark.asyncio
    async def test_streaming_response(self) -> None:
        """Test streaming response chunks."""
        clients = {
            "claude": MockModelClient("claude", response_content="Hello"),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("@claude test", stream=True):
            events.append(event)

        # Should have response chunks
        chunk_events = [e for e in events if e.type == EventType.RESPONSE_CHUNK]
        assert len(chunk_events) > 0

    @pytest.mark.asyncio
    async def test_turn_complete_aggregates_usage(self) -> None:
        """Test that TURN_COMPLETE includes aggregated usage."""
        clients = {
            "claude": MockModelClient("claude"),
            "gpt": MockModelClient("gpt"),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        events = []
        async for event in orchestrator.process_message("@all test"):
            events.append(event)

        turn_complete = next(e for e in events if e.type == EventType.TURN_COMPLETE)

        # Should have usage from both models
        if turn_complete.usage:
            assert turn_complete.usage.total_tokens > 0


class TestOrchestratorState:
    """Tests for orchestrator state management."""

    def test_add_message(self) -> None:
        """Test adding messages manually."""
        clients = {"claude": MockModelClient("claude")}
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        orchestrator.add_message(Message.user("test"))
        assert len(orchestrator.conversation) == 1

    def test_clear_conversation(self) -> None:
        """Test clearing conversation."""
        clients = {"claude": MockModelClient("claude")}
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        orchestrator.add_message(Message.user("test"))
        orchestrator.pin_message("msg1")

        orchestrator.clear_conversation()

        assert len(orchestrator.conversation) == 0
        assert len(orchestrator.pinned_ids) == 0

    def test_pin_unpin_message(self) -> None:
        """Test pinning and unpinning messages."""
        clients = {"claude": MockModelClient("claude")}
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        orchestrator.pin_message("msg1")
        assert "msg1" in orchestrator.pinned_ids

        orchestrator.unpin_message("msg1")
        assert "msg1" not in orchestrator.pinned_ids

    def test_get_model_status(self) -> None:
        """Test getting model status."""
        clients = {
            "claude": MockModelClient("claude", is_available=True),
            "gpt": MockModelClient("gpt", is_available=False),
        }
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        status = orchestrator.get_model_status()

        assert status["claude"]["available"] is True
        assert status["gpt"]["available"] is False


class TestRetryAndForceSpeak:
    """Tests for retry and force speak functionality."""

    @pytest.mark.asyncio
    async def test_retry_model(self) -> None:
        """Test retrying a specific model."""
        clients = {"claude": MockModelClient("claude", response_content="Retry response")}
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)

        # Add some context first
        orchestrator.add_message(Message.user("test"))

        events = []
        async for event in orchestrator.retry_model("claude"):
            events.append(event)

        response_events = [e for e in events if e.type == EventType.RESPONSE_COMPLETE]
        assert len(response_events) == 1
        assert response_events[0].model == "claude"

    @pytest.mark.asyncio
    async def test_force_speak(self) -> None:
        """Test forcing a model to speak."""
        clients = {"claude": MockModelClient("claude")}
        settings = create_test_settings()

        orchestrator = Orchestrator(clients, settings)
        orchestrator.add_message(Message.user("test"))

        events = []
        async for event in orchestrator.force_speak("claude"):
            events.append(event)

        # Should have forced speaker decision
        will_speak = [e for e in events if e.type == EventType.WILL_SPEAK]
        assert len(will_speak) == 1
        assert will_speak[0].decision.is_forced is True
