"""Claude (Anthropic) model client implementation."""

import json
import logging
import os
from typing import Any, AsyncIterator, Optional

from .base import (
    APIError,
    AuthenticationError,
    ModelClient,
    RateLimitError,
    with_retry,
)
from .tools import ToolDefinition, tools_to_anthropic
from .types import (
    FinishReason,
    Message,
    MessageRole,
    ModelResponse,
    StreamChunk,
    ToolCall,
    Usage,
    estimate_cost,
)

logger = logging.getLogger(__name__)


class ClaudeClient(ModelClient):
    """Client for Anthropic's Claude models."""

    name = "claude"
    display_name = "Claude"
    color = "#E07B53"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model_id, max_tokens, temperature)

        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        # Lazy import to avoid import errors when anthropic not installed
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    def _default_model_id(self) -> str:
        return "claude-opus-4-5-20251101"

    @property
    def is_available(self) -> bool:
        return self.api_key is not None

    def _convert_messages(
        self, messages: list[Message], system: Optional[str] = None
    ) -> tuple[Optional[str], list[dict[str, Any]]]:
        """Convert unified messages to Anthropic format.

        Returns:
            Tuple of (system_message, messages_list)
        """
        anthropic_messages = []
        system_content = system

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Anthropic requires system as separate parameter
                system_content = msg.content
                continue

            if msg.role == MessageRole.USER:
                anthropic_messages.append({"role": "user", "content": msg.content})

            elif msg.role == MessageRole.ASSISTANT:
                # Check if this is from another model
                is_other_model = msg.model and msg.model.lower() != self.name.lower()

                if is_other_model:
                    # Other model's response - represent as a user message
                    # reporting what the other model said. This prevents Claude
                    # from thinking it said things that other models said.
                    anthropic_messages.append({
                        "role": "user",
                        "content": f"[{msg.model} says]: {msg.content}",
                    })
                else:
                    # Our own previous response
                    content: list[dict[str, Any]] = []

                    # Add text content if present
                    if msg.content:
                        content.append({"type": "text", "text": msg.content})

                    # Add tool use blocks if present
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })

                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content if content else msg.content,
                    })

            elif msg.role == MessageRole.TOOL:
                # Find tool_call_ids that belong to OUR previous assistant messages
                # by searching backwards through the ORIGINAL messages list
                our_tool_ids: set[str] = set()
                msg_index = messages.index(msg)
                for prev_msg in reversed(messages[:msg_index]):
                    if prev_msg.role == MessageRole.ASSISTANT:
                        is_ours = not prev_msg.model or prev_msg.model.lower() == self.name.lower()
                        if is_ours and prev_msg.tool_calls:
                            for tc in prev_msg.tool_calls:
                                our_tool_ids.add(tc.id)
                        # Keep searching - there might be multiple assistant messages with tools

                # Process each tool result based on ownership
                for result in msg.tool_results:
                    if result.tool_call_id in our_tool_ids:
                        # Our tool call - use native Anthropic format
                        anthropic_messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": result.tool_call_id,
                                "content": result.content,
                                "is_error": result.is_error,
                            }],
                        })
                    else:
                        # Other model's tool call - convert to user message
                        status = "Error" if result.is_error else "Success"
                        content = result.content
                        if len(content) > 2000:
                            content = content[:1997] + "..."
                        anthropic_messages.append({
                            "role": "user",
                            "content": f"[Tool Result ({status})]: {content}",
                        })

        return system_content, anthropic_messages

    def _parse_response(self, response: Any) -> ModelResponse:
        """Parse Anthropic response to unified format."""
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        # Determine finish reason
        if response.stop_reason == "tool_use":
            finish_reason = FinishReason.TOOL_USE
        elif response.stop_reason == "max_tokens":
            finish_reason = FinishReason.LENGTH
        else:
            finish_reason = FinishReason.STOP

        # Build usage info
        usage = Usage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
        usage.cost_estimate = estimate_cost(self.model_id, usage)

        return ModelResponse(
            content="\n".join(content_parts),
            model=self.name,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage=usage,
            raw_response=response,
        )

    def _handle_api_error(self, e: Exception) -> None:
        """Convert Anthropic exceptions to our error types."""
        try:
            import anthropic

            if isinstance(e, anthropic.RateLimitError):
                raise RateLimitError(str(e))
            elif isinstance(e, anthropic.AuthenticationError):
                raise AuthenticationError(str(e))
            elif isinstance(e, anthropic.APIError):
                raise APIError(str(e), getattr(e, "status_code", None))
        except ImportError:
            pass
        raise APIError(str(e))

    @with_retry(max_retries=3)
    async def generate(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Generate a response from Claude."""
        if not self.is_available:
            raise AuthenticationError("Anthropic API key not configured")

        client = self._get_client()
        system_content, anthropic_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": anthropic_messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_anthropic(tools)

        try:
            response = await client.messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            self._handle_api_error(e)
            raise  # This line won't be reached but satisfies type checker

    async def generate_stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response from Claude."""
        if not self.is_available:
            raise AuthenticationError("Anthropic API key not configured")

        client = self._get_client()
        system_content, anthropic_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": anthropic_messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_anthropic(tools)

        try:
            async with client.messages.stream(**kwargs) as stream:
                current_tool_call: Optional[dict[str, Any]] = None
                tool_input_json = ""

                async for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, "type"):
                            if event.content_block.type == "tool_use":
                                current_tool_call = {
                                    "id": event.content_block.id,
                                    "name": event.content_block.name,
                                }
                                tool_input_json = ""

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield StreamChunk(content=event.delta.text)
                        elif hasattr(event.delta, "partial_json"):
                            tool_input_json += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_call:
                            try:
                                arguments = json.loads(tool_input_json) if tool_input_json else {}
                            except json.JSONDecodeError:
                                arguments = {}

                            yield StreamChunk(
                                tool_call=ToolCall(
                                    id=current_tool_call["id"],
                                    name=current_tool_call["name"],
                                    arguments=arguments,
                                )
                            )
                            current_tool_call = None

                    elif event.type == "message_stop":
                        # Get final message for usage info
                        final_message = await stream.get_final_message()
                        usage = Usage(
                            prompt_tokens=final_message.usage.input_tokens,
                            completion_tokens=final_message.usage.output_tokens,
                            total_tokens=(
                                final_message.usage.input_tokens
                                + final_message.usage.output_tokens
                            ),
                        )
                        usage.cost_estimate = estimate_cost(self.model_id, usage)

                        finish_reason = (
                            FinishReason.TOOL_USE
                            if final_message.stop_reason == "tool_use"
                            else FinishReason.STOP
                        )

                        yield StreamChunk(
                            is_complete=True,
                            finish_reason=finish_reason,
                            usage=usage,
                        )

        except Exception as e:
            self._handle_api_error(e)

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer.

        Falls back to rough estimate if tokenizer unavailable.
        """
        try:
            # Use rough estimate (Claude uses ~4 chars per token on average)
            # Note: Anthropic SDK doesn't expose direct token counting
            return len(text) // 4
        except (ImportError, AttributeError) as e:
            logger.debug(f"Token counting unavailable, using estimate: {e}")
            return self.estimate_tokens(text)
