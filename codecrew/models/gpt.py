"""GPT (OpenAI) model client implementation."""

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
from .tools import ToolDefinition, tools_to_openai
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


class GPTClient(ModelClient):
    """Client for OpenAI's GPT models."""

    name = "gpt"
    display_name = "GPT"
    color = "#10A37F"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model_id, max_tokens, temperature)

        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        # Lazy import
        self._client = None
        self._encoding = None

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    def _get_encoding(self) -> Any:
        """Get or create the tiktoken encoding."""
        if self._encoding is None:
            try:
                import tiktoken

                # Use cl100k_base for GPT-4 models
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                return None
        return self._encoding

    def _default_model_id(self) -> str:
        return "gpt-4o"

    @property
    def is_available(self) -> bool:
        return self.api_key is not None

    def _convert_messages(
        self, messages: list[Message], system: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Convert unified messages to OpenAI format."""
        openai_messages = []

        # Add system message first if provided
        if system:
            openai_messages.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                openai_messages.append({"role": "system", "content": msg.content})

            elif msg.role == MessageRole.USER:
                openai_messages.append({"role": "user", "content": msg.content})

            elif msg.role == MessageRole.ASSISTANT:
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or None,
                }

                # Add tool calls if present
                if msg.tool_calls:
                    message["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]

                openai_messages.append(message)

            elif msg.role == MessageRole.TOOL:
                # Tool results in OpenAI format
                for result in msg.tool_results:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    })

        return openai_messages

    def _parse_response(self, response: Any) -> ModelResponse:
        """Parse OpenAI response to unified format."""
        choice = response.choices[0]
        message = choice.message

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments,
                ))

        # Determine finish reason
        if choice.finish_reason == "tool_calls":
            finish_reason = FinishReason.TOOL_USE
        elif choice.finish_reason == "length":
            finish_reason = FinishReason.LENGTH
        elif choice.finish_reason == "content_filter":
            finish_reason = FinishReason.CONTENT_FILTER
        else:
            finish_reason = FinishReason.STOP

        # Build usage info
        usage = None
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            usage.cost_estimate = estimate_cost(self.model_id, usage)

        return ModelResponse(
            content=message.content or "",
            model=self.name,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage=usage,
            raw_response=response,
        )

    def _handle_api_error(self, e: Exception) -> None:
        """Convert OpenAI exceptions to our error types."""
        try:
            import openai

            if isinstance(e, openai.RateLimitError):
                raise RateLimitError(str(e))
            elif isinstance(e, openai.AuthenticationError):
                raise AuthenticationError(str(e))
            elif isinstance(e, openai.APIError):
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
        """Generate a response from GPT."""
        if not self.is_available:
            raise AuthenticationError("OpenAI API key not configured")

        client = self._get_client()
        openai_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": openai_messages,
            "max_completion_tokens": max_tokens or self.max_tokens,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_openai(tools)

        try:
            response = await client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            self._handle_api_error(e)
            raise

    async def generate_stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response from GPT."""
        if not self.is_available:
            raise AuthenticationError("OpenAI API key not configured")

        client = self._get_client()
        openai_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": openai_messages,
            "max_completion_tokens": max_tokens or self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_openai(tools)

        try:
            # Track tool calls being built
            current_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in await client.chat.completions.create(**kwargs):
                if not chunk.choices:
                    # Final chunk with usage info
                    if chunk.usage:
                        usage = Usage(
                            prompt_tokens=chunk.usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens,
                        )
                        usage.cost_estimate = estimate_cost(self.model_id, usage)
                        yield StreamChunk(is_complete=True, usage=usage)
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle text content
                if delta.content:
                    yield StreamChunk(content=delta.content)

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index

                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc_delta.id:
                            current_tool_calls[idx]["id"] = tc_delta.id

                        if tc_delta.function:
                            if tc_delta.function.name:
                                current_tool_calls[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                current_tool_calls[idx]["arguments"] += tc_delta.function.arguments

                # Check for finish
                if choice.finish_reason:
                    finish_reason = (
                        FinishReason.TOOL_USE
                        if choice.finish_reason == "tool_calls"
                        else FinishReason.STOP
                    )

                    # Yield completed tool calls
                    for tc_data in current_tool_calls.values():
                        try:
                            arguments = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            arguments = {}

                        yield StreamChunk(
                            tool_call=ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=arguments,
                            )
                        )

                    yield StreamChunk(is_complete=True, finish_reason=finish_reason)

        except Exception as e:
            self._handle_api_error(e)

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        encoding = self._get_encoding()
        if encoding:
            return len(encoding.encode(text))
        return self.estimate_tokens(text)
