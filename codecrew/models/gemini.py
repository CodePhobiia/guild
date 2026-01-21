"""Gemini (Google) model client implementation using the new google.genai SDK."""

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
from .tools import ToolDefinition
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
    """Client for Google's Gemini models using the new google.genai SDK."""

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
        # New SDK checks GEMINI_API_KEY, but we also support GOOGLE_API_KEY for backwards compat
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        # Lazy initialization of client
        self._client = None
        self._async_client = None

    def _get_client(self) -> Any:
        """Get or create the synchronous Gemini client."""
        if self._client is None and self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. "
                    "Run: pip install google-genai"
                )
        return self._client

    def _get_async_client(self) -> Any:
        """Get or create the async Gemini client."""
        if self._async_client is None and self.api_key:
            try:
                from google import genai
                # The async client is accessed via .aio property
                client = genai.Client(api_key=self.api_key)
                self._async_client = client.aio
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. "
                    "Run: pip install google-genai"
                )
        return self._async_client

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

                if parts:
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

    def _build_tools_config(self, tools: Optional[list[ToolDefinition]]) -> Optional[list[dict]]:
        """Build tools configuration for Gemini API."""
        if not tools:
            return None

        # Convert tools to Google format (function declarations)
        function_declarations = []
        for tool in tools:
            function_declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool._build_json_schema(),
            })

        return function_declarations

    def _parse_response(self, response: Any) -> ModelResponse:
        """Parse Gemini response to unified format."""
        content_parts = []
        tool_calls = []

        try:
            # Access text directly if available
            if hasattr(response, "text") and response.text:
                content_parts.append(response.text)

            # Check for candidates with parts
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    parts = getattr(candidate.content, "parts", None)
                    if parts:
                        for part in parts:
                            try:
                                # Check for text
                                if hasattr(part, "text") and part.text and part.text not in content_parts:
                                    content_parts.append(part.text)
                                # Check for function call
                                elif hasattr(part, "function_call") and part.function_call:
                                    fc = part.function_call
                                    # Get function name and args
                                    fc_name = getattr(fc, "name", None)
                                    fc_args = getattr(fc, "args", None)

                                    if fc_name:
                                        # Convert args to dict
                                        args = {}
                                        if fc_args:
                                            try:
                                                args = dict(fc_args)
                                            except (TypeError, ValueError):
                                                # Try accessing as object attributes
                                                if hasattr(fc_args, "items"):
                                                    args = dict(fc_args.items())

                                        tool_calls.append(ToolCall(
                                            id=f"call_{fc_name}_{len(tool_calls)}",
                                            name=fc_name,
                                            arguments=args,
                                        ))
                            except Exception as e:
                                logger.debug(f"Error parsing part: {e}")
                                continue
        except Exception as e:
            logger.debug(f"Error parsing response: {e}")

        # Determine finish reason
        finish_reason = FinishReason.STOP
        if tool_calls:
            finish_reason = FinishReason.TOOL_USE
        elif hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
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
        error_msg = str(e)

        # Try to extract better error message
        if hasattr(e, "message"):
            error_msg = str(e.message)
        elif hasattr(e, "args") and e.args:
            error_msg = str(e.args[0])

        # If error message is unhelpful, include exception type
        if not error_msg or error_msg in ("", "object", "'object'"):
            error_msg = f"{type(e).__name__}: {repr(e)}"

        error_str = error_msg.lower()

        if "quota" in error_str or "rate" in error_str or "429" in error_str or "resource_exhausted" in error_str:
            raise RateLimitError(error_msg)
        elif "api key" in error_str or "authentication" in error_str or "invalid" in error_str or "unauthenticated" in error_str:
            raise AuthenticationError(error_msg)
        else:
            raise APIError(error_msg)

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
            from google.genai import types

            async_client = self._get_async_client()
            system_instruction, contents = self._convert_messages(messages, system)

            # Build generation config
            config_kwargs = {
                "max_output_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }

            # Add system instruction
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            # Add tools if provided
            tools_config = self._build_tools_config(tools)
            if tools_config:
                config_kwargs["tools"] = tools_config

            config = types.GenerateContentConfig(**config_kwargs)

            response = await async_client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )

            return self._parse_response(response)

        except Exception as e:
            self._handle_api_error(e)
            raise  # pragma: no cover

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
            from google.genai import types

            async_client = self._get_async_client()
            system_instruction, contents = self._convert_messages(messages, system)

            # Build generation config
            config_kwargs = {
                "max_output_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }

            # Add system instruction
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            # Add tools if provided
            tools_config = self._build_tools_config(tools)
            if tools_config:
                config_kwargs["tools"] = tools_config

            config = types.GenerateContentConfig(**config_kwargs)

            collected_tool_calls = []
            total_usage = None

            # Use the streaming method
            async for chunk in async_client.models.generate_content_stream(
                model=self.model_id,
                contents=contents,
                config=config,
            ):
                try:
                    # Try to get text from chunk
                    if hasattr(chunk, "text") and chunk.text:
                        yield StreamChunk(content=chunk.text)

                    # Check for function calls in candidates
                    if hasattr(chunk, "candidates") and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, "content") and candidate.content:
                            parts = getattr(candidate.content, "parts", None)
                            if parts:
                                for part in parts:
                                    try:
                                        if hasattr(part, "function_call") and part.function_call:
                                            fc = part.function_call
                                            fc_name = getattr(fc, "name", None)
                                            fc_args = getattr(fc, "args", None)

                                            if fc_name:
                                                args = {}
                                                if fc_args:
                                                    try:
                                                        args = dict(fc_args)
                                                    except (TypeError, ValueError):
                                                        if hasattr(fc_args, "items"):
                                                            args = dict(fc_args.items())

                                                collected_tool_calls.append(ToolCall(
                                                    id=f"call_{fc_name}_{len(collected_tool_calls)}",
                                                    name=fc_name,
                                                    arguments=args,
                                                ))
                                    except Exception as e:
                                        logger.debug(f"Error processing part in stream: {e}")
                                        continue

                    # Capture usage metadata if available
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        meta = chunk.usage_metadata
                        total_usage = Usage(
                            prompt_tokens=getattr(meta, "prompt_token_count", 0),
                            completion_tokens=getattr(meta, "candidates_token_count", 0),
                            total_tokens=getattr(meta, "total_token_count", 0),
                        )
                        total_usage.cost_estimate = estimate_cost(self.model_id, total_usage)

                except Exception as e:
                    logger.debug(f"Error processing stream chunk: {e}")
                    continue

            # Yield tool calls at the end
            for tc in collected_tool_calls:
                yield StreamChunk(tool_call=tc)

            # Final chunk
            finish_reason = FinishReason.TOOL_USE if collected_tool_calls else FinishReason.STOP

            yield StreamChunk(
                is_complete=True,
                finish_reason=finish_reason,
                usage=total_usage,
            )

        except Exception as e:
            self._handle_api_error(e)

    def count_tokens(self, text: str) -> int:
        """Count tokens using Gemini's tokenizer."""
        try:
            client = self._get_client()
            if client:
                response = client.models.count_tokens(
                    model=self.model_id,
                    contents=text,
                )
                return response.total_tokens
        except Exception as e:
            logger.debug(f"Gemini token counting failed, using estimate: {type(e).__name__}: {e}")

        return self.estimate_tokens(text)
