"""Tests for speaking evaluation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecrew.models.types import Message, ModelResponse, FinishReason
from codecrew.orchestrator.events import SpeakerDecision
from codecrew.orchestrator.speaking import SpeakingEvaluator, evaluate_speakers


class MockModelClient:
    """Mock model client for testing."""

    def __init__(
        self,
        name: str = "test",
        response_content: str = '{"should_speak": true, "confidence": 0.8, "reason": "test"}',
        is_available: bool = True,
        delay: float = 0.0,
    ):
        self.name = name
        self.display_name = name.title()
        self.color = "#000000"
        self.model_id = f"{name}-test"
        self._response_content = response_content
        self._is_available = is_available
        self._delay = delay

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
        if self._delay:
            await asyncio.sleep(self._delay)
        return ModelResponse(
            content=self._response_content,
            model=self.name,
            finish_reason=FinishReason.STOP,
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class TestSpeakingEvaluator:
    """Tests for SpeakingEvaluator class."""

    @pytest.mark.asyncio
    async def test_evaluate_all_parallel(self) -> None:
        """Test that all models are evaluated in parallel."""
        clients = {
            "claude": MockModelClient("claude"),
            "gpt": MockModelClient("gpt"),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test message",
        )

        assert len(decisions) == 2
        model_names = {d.model for d in decisions}
        assert model_names == {"claude", "gpt"}

    @pytest.mark.asyncio
    async def test_forced_speakers(self) -> None:
        """Test that forced speakers are always marked to speak."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='{"should_speak": false, "confidence": 0.1, "reason": "nothing"}',
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
            forced_speakers=["claude"],
        )

        assert len(decisions) == 1
        assert decisions[0].should_speak is True
        assert decisions[0].is_forced is True

    @pytest.mark.asyncio
    async def test_unavailable_model_skipped(self) -> None:
        """Test that unavailable models are skipped."""
        clients = {
            "claude": MockModelClient("claude", is_available=True),
            "gpt": MockModelClient("gpt", is_available=False),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
        )

        assert len(decisions) == 1
        assert decisions[0].model == "claude"

    @pytest.mark.asyncio
    async def test_silence_threshold(self) -> None:
        """Test that models below threshold stay silent."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='{"should_speak": true, "confidence": 0.2, "reason": "low conf"}',
            ),
        }

        evaluator = SpeakingEvaluator(clients, silence_threshold=0.5)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
        )

        assert len(decisions) == 1
        assert decisions[0].should_speak is False  # Below threshold

    @pytest.mark.asyncio
    async def test_sorted_by_confidence(self) -> None:
        """Test that results are sorted by confidence descending."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='{"should_speak": true, "confidence": 0.5, "reason": "medium"}',
            ),
            "gpt": MockModelClient(
                "gpt",
                response_content='{"should_speak": true, "confidence": 0.9, "reason": "high"}',
            ),
            "gemini": MockModelClient(
                "gemini",
                response_content='{"should_speak": true, "confidence": 0.7, "reason": "moderate"}',
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
        )

        confidences = [d.confidence for d in decisions]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test that timeouts are handled gracefully."""
        clients = {
            "claude": MockModelClient("claude", delay=10.0),  # Will timeout
        }

        evaluator = SpeakingEvaluator(clients, timeout=0.1)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
        )

        # Should still get a decision (defaults to speaking on timeout)
        assert len(decisions) == 1
        assert decisions[0].should_speak is True
        assert "timed out" in decisions[0].reason.lower()

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """Test that errors are handled gracefully."""
        client = MockModelClient("claude")
        client.generate = AsyncMock(side_effect=Exception("API Error"))

        clients = {"claude": client}

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all(
            conversation=[],
            user_message="test",
        )

        # Should still get a decision (defaults to speaking on error)
        assert len(decisions) == 1
        assert decisions[0].should_speak is True


class TestResponseParsing:
    """Tests for parsing model responses."""

    @pytest.mark.asyncio
    async def test_parse_clean_json(self) -> None:
        """Test parsing clean JSON response."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='{"should_speak": true, "confidence": 0.8, "reason": "I have input"}',
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all([], "test")

        assert decisions[0].should_speak is True
        assert decisions[0].confidence == 0.8
        assert decisions[0].reason == "I have input"

    @pytest.mark.asyncio
    async def test_parse_markdown_json(self) -> None:
        """Test parsing JSON in markdown code block."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='```json\n{"should_speak": false, "confidence": 0.3, "reason": "covered"}\n```',
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all([], "test")

        assert decisions[0].should_speak is False
        assert decisions[0].confidence == 0.3

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON defaults to speaking."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content="This is not JSON at all",
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all([], "test")

        # Should default to speaking on parse failure
        assert decisions[0].should_speak is True
        assert decisions[0].confidence == 0.5

    @pytest.mark.asyncio
    async def test_parse_partial_json(self) -> None:
        """Test parsing JSON with extra text."""
        clients = {
            "claude": MockModelClient(
                "claude",
                response_content='Sure! Here is my decision: {"should_speak": true, "confidence": 0.7, "reason": "test"} Hope that helps!',
            ),
        }

        evaluator = SpeakingEvaluator(clients)
        decisions = await evaluator.evaluate_all([], "test")

        # Should extract the JSON from the text
        assert decisions[0].should_speak is True
        assert decisions[0].confidence == 0.7


class TestEvaluateSpeakers:
    """Tests for evaluate_speakers convenience function."""

    @pytest.mark.asyncio
    async def test_convenience_function(self) -> None:
        """Test the convenience function."""
        clients = {
            "claude": MockModelClient("claude"),
        }

        decisions = await evaluate_speakers(
            clients=clients,
            conversation=[],
            user_message="test",
        )

        assert len(decisions) == 1
        assert decisions[0].model == "claude"
