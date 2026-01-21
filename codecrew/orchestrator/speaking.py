"""Speaking evaluation for the orchestrator.

Determines which models should contribute to the conversation by:
1. Querying all models in parallel with the "should speak?" prompt
2. Parsing their JSON responses
3. Handling forced speakers from @mentions
4. Sorting by confidence
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

from codecrew.models.base import ModelClient
from codecrew.models.types import Message, ModelResponse

from .events import SpeakerDecision
from .prompts import format_should_speak_prompt

logger = logging.getLogger(__name__)

# Timeout for "should speak?" evaluation per model
EVALUATION_TIMEOUT = 5.0  # seconds

# Default silence threshold - models below this confidence stay silent
DEFAULT_SILENCE_THRESHOLD = 0.3


class SpeakingEvaluator:
    """Evaluates which models should speak in the conversation.

    Uses parallel API calls to minimize latency, with timeout handling
    and graceful degradation when models fail to respond.
    """

    def __init__(
        self,
        clients: dict[str, ModelClient],
        silence_threshold: float = DEFAULT_SILENCE_THRESHOLD,
        timeout: float = EVALUATION_TIMEOUT,
    ):
        """Initialize the speaking evaluator.

        Args:
            clients: Dictionary mapping model names to client instances
            silence_threshold: Minimum confidence to speak (0-1)
            timeout: Timeout in seconds for each evaluation
        """
        self.clients = clients
        self.silence_threshold = silence_threshold
        self.timeout = timeout

    async def evaluate_all(
        self,
        conversation: list[Message],
        user_message: str,
        previous_responses: Optional[list[tuple[str, str]]] = None,
        forced_speakers: Optional[list[str]] = None,
    ) -> list[SpeakerDecision]:
        """Evaluate all models to determine who should speak.

        Args:
            conversation: The conversation history
            user_message: The user's latest message
            previous_responses: Responses already generated this turn (model, content)
            forced_speakers: Models forced to speak via @mentions

        Returns:
            List of SpeakerDecision objects, sorted by confidence descending
        """
        forced = set(forced_speakers or [])

        # Build evaluation tasks for all models
        tasks = []
        model_names = list(self.clients.keys())

        for model_name, client in self.clients.items():
            if not client.is_available:
                logger.debug(f"Skipping {model_name} - not available")
                continue

            # Check if forced to speak
            is_forced = model_name in forced

            # Create evaluation task
            task = self._evaluate_single(
                model_name=model_name,
                client=client,
                conversation=conversation,
                user_message=user_message,
                previous_responses=previous_responses,
                other_models=[m for m in model_names if m != model_name],
                is_forced=is_forced,
            )
            tasks.append(task)

        # Run all evaluations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, handling exceptions
        decisions = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Evaluation failed: {result}")
            elif result is not None:
                decisions.append(result)

        # Sort by confidence descending
        decisions.sort(key=lambda d: d.confidence, reverse=True)

        return decisions

    async def _evaluate_single(
        self,
        model_name: str,
        client: ModelClient,
        conversation: list[Message],
        user_message: str,
        previous_responses: Optional[list[tuple[str, str]]],
        other_models: list[str],
        is_forced: bool,
    ) -> SpeakerDecision:
        """Evaluate a single model's desire to speak.

        Args:
            model_name: Name of the model
            client: Model client instance
            conversation: Conversation history
            user_message: Latest user message
            previous_responses: Earlier responses this turn
            other_models: Names of other models
            is_forced: Whether model is forced via @mention

        Returns:
            SpeakerDecision for this model
        """
        # If forced, return immediately with forced decision
        if is_forced:
            return SpeakerDecision.forced(model_name)

        try:
            # Format conversation history for prompt
            history = self._format_conversation(conversation)

            # Build the evaluation prompt
            prompt = format_should_speak_prompt(
                model_name=client.display_name,
                other_models=[self.clients[m].display_name for m in other_models if m in self.clients],
                conversation_history=history,
                user_message=user_message,
                previous_responses=previous_responses,
            )

            # Query the model with timeout
            messages = [Message.user(prompt)]

            response = await asyncio.wait_for(
                client.generate(
                    messages=messages,
                    max_tokens=150,  # Short response expected
                    temperature=0.3,  # Lower temperature for more consistent decisions
                ),
                timeout=self.timeout,
            )

            # Parse the response
            decision = self._parse_response(model_name, response)

            # Apply silence threshold
            if decision.confidence < self.silence_threshold:
                return SpeakerDecision.silent(
                    model=model_name,
                    confidence=decision.confidence,
                    reason=f"Below threshold ({decision.confidence:.2f} < {self.silence_threshold})",
                )

            return decision

        except asyncio.TimeoutError:
            logger.warning(f"{model_name} evaluation timed out")
            # On timeout, default to speaking with medium confidence
            return SpeakerDecision.speak(
                model=model_name,
                confidence=0.5,
                reason="Evaluation timed out - defaulting to speak",
            )

        except Exception as e:
            logger.error(f"{model_name} evaluation error: {e}")
            # On error, default to speaking with low confidence
            return SpeakerDecision.speak(
                model=model_name,
                confidence=0.4,
                reason=f"Evaluation error - defaulting to speak",
            )

    def _parse_response(
        self,
        model_name: str,
        response: ModelResponse,
    ) -> SpeakerDecision:
        """Parse the model's response into a SpeakerDecision.

        Handles various response formats including:
        - Clean JSON
        - JSON wrapped in markdown code blocks
        - Malformed JSON with common issues

        Args:
            model_name: Name of the model
            response: The model's response

        Returns:
            Parsed SpeakerDecision
        """
        content = response.content.strip()

        # Try to extract JSON from response
        json_data = self._extract_json(content)

        if json_data is None:
            logger.warning(f"{model_name} returned unparseable response: {content[:100]}")
            # Default to speaking on parse failure
            return SpeakerDecision.speak(
                model=model_name,
                confidence=0.5,
                reason="Could not parse response - defaulting to speak",
            )

        # Extract fields with defaults
        should_speak = json_data.get("should_speak", True)
        confidence = float(json_data.get("confidence", 0.5))
        reason = str(json_data.get("reason", "No reason provided"))

        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))

        if should_speak:
            return SpeakerDecision.speak(
                model=model_name,
                confidence=confidence,
                reason=reason,
            )
        else:
            return SpeakerDecision.silent(
                model=model_name,
                confidence=confidence,
                reason=reason,
            )

    def _extract_json(self, content: str) -> Optional[dict[str, Any]]:
        """Extract JSON from response content.

        Handles markdown code blocks and common formatting issues.

        Args:
            content: The response content

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        # Try direct JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(code_block_pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object anywhere in content
        json_pattern = r"\{[^{}]*\"should_speak\"[^{}]*\}"
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Try fixing common issues
        # Replace single quotes with double quotes
        fixed = content.replace("'", '"')
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # Handle true/false without quotes
        fixed = re.sub(r"\bTrue\b", "true", content)
        fixed = re.sub(r"\bFalse\b", "false", fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        return None

    def _format_conversation(
        self,
        conversation: list[Message],
        max_messages: int = 10,
    ) -> str:
        """Format conversation history for the prompt.

        Args:
            conversation: List of messages
            max_messages: Maximum number of recent messages to include

        Returns:
            Formatted conversation string
        """
        if not conversation:
            return "(No previous messages)"

        # Take most recent messages
        recent = conversation[-max_messages:]

        lines = []
        for msg in recent:
            role = msg.role.value.upper()
            model_tag = f" [{msg.model}]" if msg.model else ""
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            lines.append(f"{role}{model_tag}: {content}")

        return "\n\n".join(lines)


async def evaluate_speakers(
    clients: dict[str, ModelClient],
    conversation: list[Message],
    user_message: str,
    forced_speakers: Optional[list[str]] = None,
    silence_threshold: float = DEFAULT_SILENCE_THRESHOLD,
) -> list[SpeakerDecision]:
    """Convenience function to evaluate which models should speak.

    Args:
        clients: Model clients
        conversation: Conversation history
        user_message: Latest user message
        forced_speakers: Models forced to speak
        silence_threshold: Minimum confidence to speak

    Returns:
        Sorted list of speaker decisions
    """
    evaluator = SpeakingEvaluator(
        clients=clients,
        silence_threshold=silence_threshold,
    )

    return await evaluator.evaluate_all(
        conversation=conversation,
        user_message=user_message,
        forced_speakers=forced_speakers,
    )
