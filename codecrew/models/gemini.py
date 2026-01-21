"""Gemini (Google) model client implementation."""

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
from .tools import ToolDefinition, tools_to_google
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


class GeminiClient(ModelClient):
    """Client for Google's Gemini models."""

    name = "gemini"
    display_name = "Gemini"
    color = "#4285F4"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        super().__init__(api_key, model_id, max_tokens, temperature)

        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")

        # Lazy initialization
        self._model = None
        self._configured = False

    def _configure(self) -> None:
        """Configure the Google Generative AI SDK."""
        if not self._configured and self.api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._configured = True
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )

    def _get_model(self, tools: Optional[list[ToolDefinition]] = None) -> Any:
        """Get or create the Gemini model."""
        self._configure()

        try:
            import google.generativeai as genai

            # Prepare tools if provided
            tool_config = None
            if tools:
                google_tools = tools_to_google(tools)
                tool_config = [genai.protos.Tool(function_declarations=google_tools)]

            return genai.GenerativeModel(
                model_name=self.model_id,
                tools=tool_config,
            )
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

    def _default_model_id(self) -> str:
        return "gemini-2.0-flash"

    @property
    def is_available(self) -> bool:
        return self.api_key is not None

    def _convert_messages(
        self, messages: list[Message], system: Optional[str] = None
    ) -> tuple[Optional[str], list[dict[str, Any]]]:
        """Convert unified messages to Gemini format.

        Returns:
            Tuple of (system_instruction, contents)
        """
        system_instruction = system
        contents = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content
                continue

            if msg.role == MessageRole.USER:
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg.content}],
                })

            elif msg.role == MessageRole.ASSISTANT:
                parts = []

                if msg.content:
                    parts.append({"text": msg.content})

                # Add function calls if present
                for tc in msg.tool_calls:
                    parts.append({
                        "function_call": {
                            "name": tc.name,
                            "args": tc.arguments,
                        }
                    })

                contents.append({
                    "role": "model",
                    "parts": parts,
                })

            elif msg.role == MessageRole.TOOL:
                # Function responses in Gemini format
                for result in msg.tool_results:
                    contents.append({
                        "role": "user",
                        "parts": [{
                            "function_response": {
                                "name": msg.name or "unknown",
                                "response": {"result": result.content},
                            }
                        }],
                    })

        return system_instruction, contents

    def _parse_response(self, response: Any) -> ModelResponse:
        """Parse Gemini response to unified format."""
        content_parts = []
        tool_calls = []

        # Handle the response
        candidate = response.candidates[0] if response.candidates else None

        if candidate:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content_parts.append(part.text)
                elif hasattr(part, "function_call"):
                    fc = part.function_call
                    # Convert protobuf Struct to dict
                    args = dict(fc.args) if fc.args else {}
                    tool_calls.append(ToolCall(
                        id=f"call_{fc.name}_{len(tool_calls)}",
                        name=fc.name,
                        arguments=args,
                    ))

        # Determine finish reason
        finish_reason = FinishReason.STOP
        if candidate:
            if hasattr(candidate, "finish_reason"):
                reason = str(candidate.finish_reason).lower()
                if "tool" in reason or "function" in reason:
                    finish_reason = FinishReason.TOOL_USE
                elif "length" in reason or "max" in reason:
                    finish_reason = FinishReason.LENGTH
                elif "safety" in reason:
                    finish_reason = FinishReason.CONTENT_FILTER

        # Build usage info
        usage = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage = Usage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0),
                completion_tokens=getattr(meta, "candidates_token_count", 0),
                total_tokens=getattr(meta, "total_token_count", 0),
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
        """Convert Google API exceptions to our error types."""
        error_str = str(e).lower()

        if "quota" in error_str or "rate" in error_str:
            raise RateLimitError(str(e))
        elif "api key" in error_str or "authentication" in error_str or "invalid" in error_str:
            raise AuthenticationError(str(e))
        else:
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
        """Generate a response from Gemini."""
        if not self.is_available:
            raise AuthenticationError("Google API key not configured")

        try:
            model = self._get_model(tools)
            system_instruction, contents = self._convert_messages(messages, system)

            # Build generation config
            generation_config = {
                "max_output_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }

            # Create chat or generate
            if system_instruction:
                # For system instructions, we need to use a model with system_instruction
                import google.generativeai as genai

                tool_config = None
                if tools:
                    google_tools = tools_to_google(tools)
                    tool_config = [genai.protos.Tool(function_declarations=google_tools)]

                model = genai.GenerativeModel(
                    model_name=self.model_id,
                    system_instruction=system_instruction,
                    tools=tool_config,
                )

            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
            )

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
        """Generate a streaming response from Gemini."""
        if not self.is_available:
            raise AuthenticationError("Google API key not configured")

        try:
            import google.generativeai as genai

            system_instruction, contents = self._convert_messages(messages, system)

            # Build model with system instruction and tools
            tool_config = None
            if tools:
                google_tools = tools_to_google(tools)
                tool_config = [genai.protos.Tool(function_declarations=google_tools)]

            model = genai.GenerativeModel(
                model_name=self.model_id,
                system_instruction=system_instruction,
                tools=tool_config,
            )

            generation_config = {
                "max_output_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }

            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
                stream=True,
            )

            collected_tool_calls = []

            async for chunk in response:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield StreamChunk(content=part.text)
                        elif hasattr(part, "function_call"):
                            fc = part.function_call
                            args = dict(fc.args) if fc.args else {}
                            collected_tool_calls.append(ToolCall(
                                id=f"call_{fc.name}_{len(collected_tool_calls)}",
                                name=fc.name,
                                arguments=args,
                            ))

            # Yield tool calls at the end
            for tc in collected_tool_calls:
                yield StreamChunk(tool_call=tc)

            # Final chunk
            finish_reason = FinishReason.TOOL_USE if collected_tool_calls else FinishReason.STOP

            # Try to get usage info from the response
            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                usage = Usage(
                    prompt_tokens=getattr(meta, "prompt_token_count", 0),
                    completion_tokens=getattr(meta, "candidates_token_count", 0),
                    total_tokens=getattr(meta, "total_token_count", 0),
                )
                usage.cost_estimate = estimate_cost(self.model_id, usage)

            yield StreamChunk(
                is_complete=True,
                finish_reason=finish_reason,
                usage=usage,
            )

        except Exception as e:
            self._handle_api_error(e)

    def count_tokens(self, text: str) -> int:
        """Count tokens using Gemini's tokenizer."""
        try:
            self._configure()
            model = self._get_model()
            result = model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            # Fall back to estimate for any error (API errors, import issues, etc.)
            logger.debug(f"Gemini token counting failed, using estimate: {type(e).__name__}: {e}")
            return self.estimate_tokens(text)
