"""End-to-end tests for full conversation workflows.

These tests verify the high-level behavior of the orchestration system
without relying on specific internal implementation details.
"""

import pytest

from codecrew.models.types import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    Usage,
)
from codecrew.orchestrator.events import EventType, OrchestratorEvent
from codecrew.orchestrator.mentions import parse_mentions
from codecrew.config.settings import ConversationConfig, Settings, ModelsConfig


class TestMentionParsing:
    """Tests for @mention parsing functionality."""

    def test_parse_single_mention(self):
        """Test parsing a single @mention."""
        result = parse_mentions("@claude help me with this code")
        assert "claude" in result.mentions
        assert "help me with this code" in result.clean_message

    def test_parse_multiple_mentions(self):
        """Test parsing multiple @mentions."""
        result = parse_mentions("@claude @gpt what do you think?")
        assert "claude" in result.mentions
        assert "gpt" in result.mentions

    def test_parse_all_mention(self):
        """Test parsing @all mention."""
        result = parse_mentions("@all please review this")
        assert result.force_all
        assert "please review this" in result.clean_message

    def test_parse_no_mention(self):
        """Test parsing message without mentions."""
        result = parse_mentions("just a regular message")
        assert len(result.mentions) == 0
        assert result.clean_message == "just a regular message"

    def test_parse_mention_with_punctuation(self):
        """Test parsing mentions with punctuation."""
        result = parse_mentions("@claude, can you help?")
        assert "claude" in result.mentions


class TestEventTypes:
    """Tests for orchestrator event types."""

    def test_thinking_event_creation(self):
        """Test creating a THINKING event."""
        event = OrchestratorEvent.thinking()
        assert event.type == EventType.THINKING

    def test_response_complete_event_creation(self):
        """Test creating a RESPONSE_COMPLETE event."""
        response = ModelResponse(
            content="Test response",
            model="claude",
            finish_reason=FinishReason.STOP,
        )
        event = OrchestratorEvent.response_complete("claude", response)
        assert event.type == EventType.RESPONSE_COMPLETE
        assert event.model == "claude"
        assert event.response.content == "Test response"

    def test_response_start_event_creation(self):
        """Test creating a RESPONSE_START event."""
        event = OrchestratorEvent.response_start("gpt")
        assert event.type == EventType.RESPONSE_START
        assert event.model == "gpt"


class TestSettingsConfiguration:
    """Tests for settings configuration."""

    def test_default_settings(self):
        """Test creating default settings."""
        settings = Settings()
        assert settings.conversation is not None
        assert settings.models is not None

    def test_custom_conversation_config(self):
        """Test custom conversation configuration."""
        config = ConversationConfig(
            first_responder="claude",
            silence_threshold=0.5,
            max_context_tokens=50000,
        )
        assert config.first_responder == "claude"
        assert config.silence_threshold == 0.5

    def test_settings_with_custom_config(self):
        """Test settings with custom configuration."""
        settings = Settings(
            conversation=ConversationConfig(first_responder="gpt"),
        )
        assert settings.conversation.first_responder == "gpt"


class TestModelResponseTypes:
    """Tests for model response types."""

    def test_model_response_with_content(self):
        """Test model response with content."""
        response = ModelResponse(
            content="Hello, world!",
            model="claude",
            finish_reason=FinishReason.STOP,
        )
        assert response.content == "Hello, world!"
        assert response.model == "claude"
        assert response.finish_reason == FinishReason.STOP

    def test_model_response_with_usage(self):
        """Test model response with usage info."""
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        response = ModelResponse(
            content="Test",
            model="gpt",
            finish_reason=FinishReason.STOP,
            usage=usage,
        )
        assert response.usage.total_tokens == 150

    def test_finish_reasons(self):
        """Test different finish reasons."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.TOOL_USE.value == "tool_use"


class TestMessageTypes:
    """Tests for message types."""

    def test_user_message(self):
        """Test creating a user message."""
        msg = Message(
            role=MessageRole.USER,
            content="Hello!",
        )
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"

    def test_assistant_message(self):
        """Test creating an assistant message."""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hi there!",
            model="claude",
        )
        assert msg.role == MessageRole.ASSISTANT
        assert msg.model == "claude"

    def test_system_message(self):
        """Test creating a system message."""
        msg = Message(
            role=MessageRole.SYSTEM,
            content="You are a helpful assistant.",
        )
        assert msg.role == MessageRole.SYSTEM
