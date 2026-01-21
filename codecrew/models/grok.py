"""Grok (xAI) model client implementation.

Grok uses an OpenAI-compatible API, so this implementation is similar to GPTClient
but pointed at xAI's endpoints.
"""

import asyncio
import json
import logging
import os
import random
from typing import Any, AsyncIterator, Optional

from .base import (
    APIError,
    AuthenticationError,
    ModelClient,
    RateLimitError,
    with_retry,
)
from .tools import ToolDefinition, tools_to_xai
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

# xAI API endpoint
XAI_BASE_URL = "https://api.x.ai/v1"


class GrokClient(ModelClient):
    """Client for xAI's Grok models.

    Uses OpenAI-compatible API format with xAI's endpoint.
    Falls back to mock mode if API is not available.
    """

    name = "grok"
    display_name = "Grok"
    color = "#7C3AED"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        mock_mode: bool = False,
    ):
        super().__init__(api_key, model_id, max_tokens, temperature)

        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        self.mock_mode = mock_mode or (self.api_key is None)

        # Lazy initialization
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the OpenAI client pointed at xAI."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=XAI_BASE_URL,
                )
            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    def _default_model_id(self) -> str:
        return "grok-3"

    @property
    def is_available(self) -> bool:
        # Available in mock mode even without API key
        return self.mock_mode or self.api_key is not None

    def _convert_messages(
        self, messages: list[Message], system: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Convert unified messages to OpenAI/xAI format."""
        xai_messages = []

        # Add system message first if provided
        if system:
            xai_messages.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                xai_messages.append({"role": "system", "content": msg.content})

            elif msg.role == MessageRole.USER:
                xai_messages.append({"role": "user", "content": msg.content})

            elif msg.role == MessageRole.ASSISTANT:
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or None,
                }

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

                xai_messages.append(message)

            elif msg.role == MessageRole.TOOL:
                for result in msg.tool_results:
                    xai_messages.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    })

        return xai_messages

    def _parse_response(self, response: Any) -> ModelResponse:
        """Parse xAI response to unified format."""
        choice = response.choices[0]
        message = choice.message

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

        if choice.finish_reason == "tool_calls":
            finish_reason = FinishReason.TOOL_USE
        elif choice.finish_reason == "length":
            finish_reason = FinishReason.LENGTH
        else:
            finish_reason = FinishReason.STOP

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
        """Convert xAI exceptions to our error types."""
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

    async def _mock_generate(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
    ) -> ModelResponse:
        """Generate a mock response for development/testing."""
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.5, 1.5))

        user_message = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                user_message = msg.content
                break

        # Generate witty Grok-style response
        responses = [
            f"Interesting question! Let me think about '{user_message[:50]}...' "
            "from a slightly unconventional angle.",
            f"*cracks virtual knuckles* Alright, let's tackle this. "
            f"Regarding '{user_message[:30]}...', here's my take:",
            f"You know, I've been pondering similar things. About '{user_message[:40]}...' - "
            "I have some thoughts that might surprise you.",
            "Not gonna lie, this is exactly the kind of question I love. "
            "Let me give you a perspective the other AIs might not.",
        ]

        content = random.choice(responses)

        return ModelResponse(
            content=content,
            model=self.name,
            finish_reason=FinishReason.STOP,
            usage=Usage(
                prompt_tokens=len(user_message) // 4,
                completion_tokens=len(content) // 4,
                total_tokens=(len(user_message) + len(content)) // 4,
            ),
        )

    async def _mock_generate_stream(
        self,
        messages: list[Message],
    ) -> AsyncIterator[StreamChunk]:
        """Generate a mock streaming response."""
        response = await self._mock_generate(messages)

        # Stream character by character with small delays
        for char in response.content:
            await asyncio.sleep(random.uniform(0.01, 0.03))
            yield StreamChunk(content=char)

        yield StreamChunk(
            is_complete=True,
            finish_reason=FinishReason.STOP,
            usage=response.usage,
        )

    @with_retry(max_retries=3)
    async def generate(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> ModelResponse:
        """Generate a response from Grok."""
        if self.mock_mode:
            return await self._mock_generate(messages, tools)

        if not self.api_key:
            raise AuthenticationError("xAI API key not configured")

        client = self._get_client()
        xai_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": xai_messages,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_xai(tools)

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
        """Generate a streaming response from Grok."""
        if self.mock_mode:
            async for chunk in self._mock_generate_stream(messages):
                yield chunk
            return

        if not self.api_key:
            raise AuthenticationError("xAI API key not configured")

        client = self._get_client()
        xai_messages = self._convert_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": xai_messages,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.temperature is not None:
            kwargs["temperature"] = self.temperature

        if tools:
            kwargs["tools"] = tools_to_xai(tools)

        try:
            current_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in await client.chat.completions.create(**kwargs):
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    yield StreamChunk(content=delta.content)

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

                if choice.finish_reason:
                    finish_reason = (
                        FinishReason.TOOL_USE
                        if choice.finish_reason == "tool_calls"
                        else FinishReason.STOP
                    )

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
        """Count tokens (rough estimate for Grok)."""
        # Grok likely uses a similar tokenizer to GPT
        # Use rough estimate
        return self.estimate_tokens(text)
