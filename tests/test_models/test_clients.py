"""Tests for model clients."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecrew.models import (
    ClaudeClient,
    GeminiClient,
    GPTClient,
    GrokClient,
    Message,
    ModelResponse,
    get_client,
    get_enabled_clients,
)
from codecrew.models.base import AuthenticationError
from codecrew.models.types import FinishReason, ShouldSpeakResult


class TestGetClient:
    """Tests for the get_client factory function."""

    def test_get_claude_client(self) -> None:
        """Test creating a Claude client."""
        client = get_client("claude", api_key="test-key")
        assert isinstance(client, ClaudeClient)
        assert client.name == "claude"

    def test_get_gpt_client(self) -> None:
        """Test creating a GPT client."""
        client = get_client("gpt", api_key="test-key")
        assert isinstance(client, GPTClient)
        assert client.name == "gpt"

    def test_get_gemini_client(self) -> None:
        """Test creating a Gemini client."""
        client = get_client("gemini", api_key="test-key")
        assert isinstance(client, GeminiClient)
        assert client.name == "gemini"

    def test_get_grok_client(self) -> None:
        """Test creating a Grok client."""
        client = get_client("grok", api_key="test-key")
        assert isinstance(client, GrokClient)
        assert client.name == "grok"

    def test_get_unknown_client_raises(self) -> None:
        """Test that unknown model name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            get_client("unknown-model")

    def test_custom_model_id(self) -> None:
        """Test creating client with custom model ID."""
        client = get_client("claude", api_key="test", model_id="claude-3-opus")
        assert client.model_id == "claude-3-opus"


class TestClaudeClient:
    """Tests for ClaudeClient."""

    def test_default_model_id(self) -> None:
        """Test default model ID."""
        client = ClaudeClient(api_key="test")
        assert "claude" in client.model_id.lower()

    def test_is_available_with_key(self) -> None:
        """Test is_available when API key is set."""
        client = ClaudeClient(api_key="test-key")
        assert client.is_available is True

    def test_is_available_without_key(self) -> None:
        """Test is_available when API key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing key from environment
            os.environ.pop("ANTHROPIC_API_KEY", None)
            client = ClaudeClient(api_key=None)
            assert client.is_available is False

    def test_display_name_and_color(self) -> None:
        """Test display name and color attributes."""
        client = ClaudeClient(api_key="test")
        assert client.display_name == "Claude"
        assert client.color == "#E07B53"


class TestGPTClient:
    """Tests for GPTClient."""

    def test_default_model_id(self) -> None:
        """Test default model ID."""
        client = GPTClient(api_key="test")
        assert "gpt" in client.model_id.lower()

    def test_is_available_with_key(self) -> None:
        """Test is_available when API key is set."""
        client = GPTClient(api_key="test-key")
        assert client.is_available is True

    def test_display_name_and_color(self) -> None:
        """Test display name and color attributes."""
        client = GPTClient(api_key="test")
        assert client.display_name == "GPT"
        assert client.color == "#10A37F"


class TestGeminiClient:
    """Tests for GeminiClient."""

    def test_default_model_id(self) -> None:
        """Test default model ID."""
        client = GeminiClient(api_key="test")
        assert "gemini" in client.model_id.lower()

    def test_is_available_with_key(self) -> None:
        """Test is_available when API key is set."""
        client = GeminiClient(api_key="test-key")
        assert client.is_available is True

    def test_display_name_and_color(self) -> None:
        """Test display name and color attributes."""
        client = GeminiClient(api_key="test")
        assert client.display_name == "Gemini"
        assert client.color == "#4285F4"


class TestGrokClient:
    """Tests for GrokClient."""

    def test_default_model_id(self) -> None:
        """Test default model ID."""
        client = GrokClient(api_key="test")
        assert "grok" in client.model_id.lower()

    def test_is_available_with_key(self) -> None:
        """Test is_available when API key is set."""
        client = GrokClient(api_key="test-key")
        assert client.is_available is True

    def test_is_available_in_mock_mode(self) -> None:
        """Test is_available in mock mode."""
        client = GrokClient(mock_mode=True)
        assert client.is_available is True

    def test_display_name_and_color(self) -> None:
        """Test display name and color attributes."""
        client = GrokClient(api_key="test")
        assert client.display_name == "Grok"
        assert client.color == "#7C3AED"

    @pytest.mark.asyncio
    async def test_mock_generate(self) -> None:
        """Test mock generation."""
        client = GrokClient(mock_mode=True)
        messages = [Message.user("Hello, Grok!")]

        response = await client.generate(messages)

        assert isinstance(response, ModelResponse)
        assert response.model == "grok"
        assert response.finish_reason == FinishReason.STOP
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_mock_stream(self) -> None:
        """Test mock streaming."""
        client = GrokClient(mock_mode=True)
        messages = [Message.user("Hello!")]

        chunks = []
        async for chunk in client.generate_stream(messages):
            chunks.append(chunk)

        # Should have content chunks and a final complete chunk
        assert len(chunks) > 0
        assert chunks[-1].is_complete is True


class TestTokenCounting:
    """Tests for token counting."""

    def test_claude_estimate_tokens(self) -> None:
        """Test Claude token estimation."""
        client = ClaudeClient(api_key="test")
        count = client.count_tokens("Hello, world!")
        assert count > 0
        assert count < 100  # Reasonable range

    def test_gpt_estimate_tokens(self) -> None:
        """Test GPT token estimation."""
        client = GPTClient(api_key="test")
        count = client.count_tokens("Hello, world!")
        assert count > 0
        assert count < 100

    def test_gemini_estimate_tokens(self) -> None:
        """Test Gemini token estimation."""
        client = GeminiClient(api_key="test")
        count = client.count_tokens("Hello, world!")
        assert count > 0
        assert count < 100

    def test_grok_estimate_tokens(self) -> None:
        """Test Grok token estimation."""
        client = GrokClient(api_key="test")
        count = client.count_tokens("Hello, world!")
        assert count > 0
        assert count < 100


class TestShouldSpeak:
    """Tests for should_speak functionality."""

    def test_parse_should_speak_response_valid(self) -> None:
        """Test parsing valid JSON response."""
        client = ClaudeClient(api_key="test")

        result = client._parse_should_speak_response(
            '{"should_speak": true, "confidence": 0.8, "reason": "I have something to add"}'
        )

        assert result.should_speak is True
        assert result.confidence == 0.8
        assert result.reason == "I have something to add"

    def test_parse_should_speak_response_no(self) -> None:
        """Test parsing 'no' response."""
        client = ClaudeClient(api_key="test")

        result = client._parse_should_speak_response(
            '{"should_speak": false, "confidence": 0.9, "reason": "Already covered"}'
        )

        assert result.should_speak is False

    def test_parse_should_speak_response_markdown(self) -> None:
        """Test parsing response with markdown code blocks."""
        client = ClaudeClient(api_key="test")

        result = client._parse_should_speak_response(
            '```json\n{"should_speak": true, "confidence": 0.7, "reason": "test"}\n```'
        )

        assert result.should_speak is True

    def test_parse_should_speak_response_invalid(self) -> None:
        """Test parsing invalid response defaults to speaking."""
        client = ClaudeClient(api_key="test")

        result = client._parse_should_speak_response("Not valid JSON at all")

        # Should default to speaking when can't parse
        assert result.should_speak is True
        assert result.confidence == 0.5


class TestMessageConversion:
    """Tests for message format conversion."""

    def test_claude_convert_user_message(self) -> None:
        """Test converting user message for Claude."""
        client = ClaudeClient(api_key="test")
        messages = [Message.user("Hello!")]

        system, converted = client._convert_messages(messages)

        assert system is None
        assert len(converted) == 1
        assert converted[0]["role"] == "user"
        assert converted[0]["content"] == "Hello!"

    def test_claude_convert_system_message(self) -> None:
        """Test converting system message for Claude."""
        client = ClaudeClient(api_key="test")
        messages = [
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ]

        system, converted = client._convert_messages(messages)

        assert system == "You are helpful."
        assert len(converted) == 1  # System message not in messages list

    def test_gpt_convert_messages(self) -> None:
        """Test converting messages for GPT."""
        client = GPTClient(api_key="test")
        messages = [
            Message.user("Hello!"),
            Message.assistant("Hi there!"),
        ]

        converted = client._convert_messages(messages)

        assert len(converted) == 2
        assert converted[0]["role"] == "user"
        assert converted[1]["role"] == "assistant"

    def test_gpt_convert_with_system(self) -> None:
        """Test converting messages with system prompt for GPT."""
        client = GPTClient(api_key="test")
        messages = [Message.user("Hello!")]

        converted = client._convert_messages(messages, system="Be helpful.")

        assert len(converted) == 2
        assert converted[0]["role"] == "system"
        assert converted[0]["content"] == "Be helpful."
