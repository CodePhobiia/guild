"""Context assembly for the orchestrator.

Builds appropriate context windows for each model, handling:
- Token limits per model
- Pinned messages (always included)
- System prompts
- Recency-based message selection
- Optional summarization for long conversations
"""

import logging
from typing import Optional, Set

from codecrew.models.base import ModelClient
from codecrew.models.types import Message, MessageRole

from .prompts import format_system_prompt

logger = logging.getLogger(__name__)

# Default maximum tokens for context window
DEFAULT_MAX_TOKENS = 100000

# Reserve tokens for model response
RESPONSE_RESERVE = 4096

# Minimum tokens to keep for conversation (after system + pinned)
MIN_CONVERSATION_TOKENS = 2000


class ContextAssembler:
    """Assembles context windows tailored to each model's limits.

    Prioritizes content in this order:
    1. System prompt
    2. Pinned messages (user-marked important context)
    3. Recent messages (most recent first)
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        response_reserve: int = RESPONSE_RESERVE,
    ):
        """Initialize the context assembler.

        Args:
            max_tokens: Maximum tokens for context window
            response_reserve: Tokens to reserve for model response
        """
        self.max_tokens = max_tokens
        self.response_reserve = response_reserve

    def assemble_for_model(
        self,
        conversation: list[Message],
        model: ModelClient,
        other_models: list[str],
        pinned_ids: Optional[Set[str]] = None,
        include_system: bool = True,
        additional_context: Optional[str] = None,
    ) -> tuple[Optional[str], list[Message]]:
        """Assemble context for a specific model.

        Args:
            conversation: Full conversation history
            model: The model client to assemble for
            other_models: Names of other models in the chat
            pinned_ids: Message IDs that are pinned
            include_system: Whether to include system prompt
            additional_context: Extra context to include in system prompt

        Returns:
            Tuple of (system_prompt, messages) ready for the model
        """
        pinned_ids = pinned_ids or set()

        # Calculate available tokens
        available = self.max_tokens - self.response_reserve
        current_tokens = 0

        # 1. System prompt (if requested)
        system_prompt = None
        if include_system:
            other_display_names = [
                self._get_display_name(m) for m in other_models
            ]
            system_prompt = format_system_prompt(
                model_name=model.display_name,
                other_models=other_display_names,
                additional_context=additional_context,
            )
            current_tokens += model.count_tokens(system_prompt)

        # 2. Separate pinned and regular messages
        pinned_messages = []
        regular_messages = []

        for msg in conversation:
            msg_id = getattr(msg, "id", None) or str(id(msg))
            if msg_id in pinned_ids:
                pinned_messages.append(msg)
            else:
                regular_messages.append(msg)

        # 3. Add pinned messages
        included_pinned = []
        for msg in pinned_messages:
            tokens = self._estimate_message_tokens(msg, model)
            if current_tokens + tokens < available:
                included_pinned.append(msg)
                current_tokens += tokens
            else:
                logger.warning(f"Pinned message excluded due to token limit")

        # 4. Calculate remaining space for regular messages
        remaining = available - current_tokens
        if remaining < MIN_CONVERSATION_TOKENS:
            remaining = MIN_CONVERSATION_TOKENS

        # 5. Add recent messages (most recent first)
        included_regular = []
        for msg in reversed(regular_messages):
            tokens = self._estimate_message_tokens(msg, model)
            if current_tokens + tokens < available:
                included_regular.insert(0, msg)
                current_tokens += tokens
            else:
                # Stop adding messages when we hit the limit
                break

        # 6. Combine: pinned first (in order), then regular (chronological)
        result = included_pinned + included_regular

        logger.debug(
            f"Context for {model.name}: {len(result)} messages, "
            f"~{current_tokens} tokens (limit: {available})"
        )

        return system_prompt, result

    def estimate_tokens(
        self,
        messages: list[Message],
        model: ModelClient,
    ) -> int:
        """Estimate total tokens for a list of messages.

        Args:
            messages: Messages to estimate
            model: Model to use for estimation

        Returns:
            Estimated token count
        """
        total = 0
        for msg in messages:
            total += self._estimate_message_tokens(msg, model)
        return total

    def _estimate_message_tokens(
        self,
        message: Message,
        model: ModelClient,
    ) -> int:
        """Estimate tokens for a single message.

        Includes overhead for role, name, and formatting.

        Args:
            message: Message to estimate
            model: Model client for token counting

        Returns:
            Estimated token count
        """
        # Base content tokens
        tokens = model.count_tokens(message.content)

        # Add overhead for role (typically 2-4 tokens)
        tokens += 4

        # Add overhead for model name if present
        if message.model:
            tokens += model.count_tokens(message.model) + 2

        # Add overhead for tool calls
        if message.tool_calls:
            for tc in message.tool_calls:
                tokens += model.count_tokens(tc.name) + 10
                # Arguments as JSON string
                import json
                tokens += model.count_tokens(json.dumps(tc.arguments))

        return tokens

    def _get_display_name(self, model_name: str) -> str:
        """Get display name for a model.

        Args:
            model_name: Internal model name

        Returns:
            Human-readable display name
        """
        display_names = {
            "claude": "Claude",
            "gpt": "GPT",
            "gemini": "Gemini",
            "grok": "Grok",
        }
        return display_names.get(model_name, model_name.title())

    def would_exceed_limit(
        self,
        conversation: list[Message],
        new_message: Message,
        model: ModelClient,
        pinned_ids: Optional[Set[str]] = None,
    ) -> bool:
        """Check if adding a message would exceed the context limit.

        Args:
            conversation: Current conversation
            new_message: Message to potentially add
            model: Model to check against
            pinned_ids: Pinned message IDs

        Returns:
            True if adding the message would exceed the limit
        """
        current = self.estimate_tokens(conversation, model)
        new_tokens = self._estimate_message_tokens(new_message, model)
        available = self.max_tokens - self.response_reserve

        return (current + new_tokens) > available


class ContextSummarizer:
    """Summarizes conversation history when it exceeds context limits.

    Used as a fallback when sliding window isn't sufficient.
    """

    def __init__(self, summarizer_client: ModelClient):
        """Initialize with a model client for summarization.

        Args:
            summarizer_client: Model to use for generating summaries
        """
        self.client = summarizer_client

    async def summarize(
        self,
        messages: list[Message],
        max_summary_tokens: int = 1000,
    ) -> str:
        """Generate a summary of conversation messages.

        Args:
            messages: Messages to summarize
            max_summary_tokens: Target length for summary

        Returns:
            Summary text
        """
        from .prompts import format_context_summary_prompt

        # Format messages for summarization
        conversation_text = self._format_for_summary(messages)

        prompt = format_context_summary_prompt(conversation_text)

        response = await self.client.generate(
            messages=[Message.user(prompt)],
            max_tokens=max_summary_tokens,
            temperature=0.3,
        )

        return response.content

    def _format_for_summary(self, messages: list[Message]) -> str:
        """Format messages for the summarization prompt.

        Args:
            messages: Messages to format

        Returns:
            Formatted text
        """
        lines = []
        for msg in messages:
            role = msg.role.value.upper()
            model_tag = f" [{msg.model}]" if msg.model else ""
            lines.append(f"{role}{model_tag}: {msg.content}")

        return "\n\n".join(lines)


def assemble_context(
    conversation: list[Message],
    model: ModelClient,
    other_models: list[str],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    pinned_ids: Optional[Set[str]] = None,
) -> tuple[Optional[str], list[Message]]:
    """Convenience function to assemble context for a model.

    Args:
        conversation: Full conversation history
        model: Target model client
        other_models: Other model names in the chat
        max_tokens: Maximum context tokens
        pinned_ids: Pinned message IDs

    Returns:
        Tuple of (system_prompt, messages)
    """
    assembler = ContextAssembler(max_tokens=max_tokens)
    return assembler.assemble_for_model(
        conversation=conversation,
        model=model,
        other_models=other_models,
        pinned_ids=pinned_ids,
    )
