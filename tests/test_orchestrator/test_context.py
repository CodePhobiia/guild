"""Tests for context assembly."""

import pytest

from codecrew.models.types import Message, MessageRole
from codecrew.orchestrator.context import ContextAssembler, assemble_context


class MockModelClient:
    """Mock model client for testing."""

    def __init__(self, name: str = "test"):
        self.name = name
        self.display_name = name.title()
        self.color = "#000000"
        self.model_id = f"{name}-test"

    @property
    def is_available(self) -> bool:
        return True

    def count_tokens(self, text: str) -> int:
        # Simple approximation: 1 token per 4 characters
        return len(text) // 4


class TestContextAssembler:
    """Tests for ContextAssembler class."""

    def test_basic_assembly(self) -> None:
        """Test basic context assembly."""
        assembler = ContextAssembler(max_tokens=10000)
        model = MockModelClient("claude")

        conversation = [
            Message.user("Hello"),
            Message.assistant("Hi there!", model="claude"),
            Message.user("How are you?"),
        ]

        system, messages = assembler.assemble_for_model(
            conversation=conversation,
            model=model,
            other_models=["gpt", "gemini"],
        )

        assert system is not None
        assert "Claude" in system  # Model name in system prompt
        assert len(messages) == 3

    def test_respects_token_limit(self) -> None:
        """Test that token limits are respected."""
        # Very small limit
        assembler = ContextAssembler(max_tokens=100, response_reserve=20)
        model = MockModelClient("claude")

        # Create long conversation
        conversation = [
            Message.user("A" * 500),  # ~125 tokens
            Message.user("B" * 500),  # ~125 tokens
            Message.user("C" * 500),  # ~125 tokens
        ]

        system, messages = assembler.assemble_for_model(
            conversation=conversation,
            model=model,
            other_models=[],
            include_system=False,  # Skip system to simplify
        )

        # Should not include all messages due to limit
        assert len(messages) < 3

    def test_pinned_messages_prioritized(self) -> None:
        """Test that pinned messages are prioritized."""
        assembler = ContextAssembler(max_tokens=200, response_reserve=20)
        model = MockModelClient("claude")

        # Create messages with IDs
        msg1 = Message.user("First message")
        msg2 = Message.user("Important pinned message")
        msg3 = Message.user("Third message")

        # Set IDs manually for testing
        msg1_id = "msg1"
        msg2_id = "msg2"
        msg3_id = "msg3"

        # Use object IDs since Message doesn't have id attribute
        conversation = [msg1, msg2, msg3]

        system, messages = assembler.assemble_for_model(
            conversation=conversation,
            model=model,
            other_models=[],
            pinned_ids={str(id(msg2))},  # Pin the second message
            include_system=False,
        )

        # Pinned message should be included
        assert msg2 in messages

    def test_system_prompt_included(self) -> None:
        """Test that system prompt is included when requested."""
        assembler = ContextAssembler()
        model = MockModelClient("claude")

        system, messages = assembler.assemble_for_model(
            conversation=[Message.user("test")],
            model=model,
            other_models=["gpt"],
            include_system=True,
        )

        assert system is not None
        assert "Claude" in system
        assert "GPT" in system  # Other model mentioned

    def test_no_system_prompt(self) -> None:
        """Test excluding system prompt."""
        assembler = ContextAssembler()
        model = MockModelClient("claude")

        system, messages = assembler.assemble_for_model(
            conversation=[Message.user("test")],
            model=model,
            other_models=[],
            include_system=False,
        )

        assert system is None

    def test_additional_context(self) -> None:
        """Test including additional context in system prompt."""
        assembler = ContextAssembler()
        model = MockModelClient("claude")

        system, messages = assembler.assemble_for_model(
            conversation=[Message.user("test")],
            model=model,
            other_models=[],
            additional_context="Previous responses this turn...",
        )

        assert system is not None
        assert "Previous responses" in system

    def test_estimate_tokens(self) -> None:
        """Test token estimation."""
        assembler = ContextAssembler()
        model = MockModelClient("claude")

        messages = [
            Message.user("Hello world"),  # ~10 chars
            Message.assistant("Hi!", model="claude"),  # ~3 chars
        ]

        tokens = assembler.estimate_tokens(messages, model)
        assert tokens > 0

    def test_would_exceed_limit(self) -> None:
        """Test checking if message would exceed limit."""
        assembler = ContextAssembler(max_tokens=50, response_reserve=10)
        model = MockModelClient("claude")

        conversation = [Message.user("A" * 100)]  # Already ~25 tokens
        new_message = Message.user("B" * 200)  # Another ~50 tokens

        # Should exceed limit
        exceeds = assembler.would_exceed_limit(
            conversation=conversation,
            new_message=new_message,
            model=model,
        )

        assert exceeds is True

    def test_empty_conversation(self) -> None:
        """Test with empty conversation."""
        assembler = ContextAssembler()
        model = MockModelClient("claude")

        system, messages = assembler.assemble_for_model(
            conversation=[],
            model=model,
            other_models=[],
        )

        assert messages == []


class TestAssembleContext:
    """Tests for assemble_context convenience function."""

    def test_convenience_function(self) -> None:
        """Test the convenience function."""
        model = MockModelClient("claude")

        system, messages = assemble_context(
            conversation=[Message.user("test")],
            model=model,
            other_models=["gpt"],
        )

        assert system is not None
        assert len(messages) == 1
