"""Turn management for the orchestrator.

Handles:
- Determining the order in which models respond
- Rotating first responder to ensure fairness
- Different ordering strategies (rotate, confidence, fixed)
"""

from typing import Literal, Optional

from .events import SpeakerDecision

# Type alias for turn ordering strategies
TurnStrategy = Literal["rotate", "confidence", "fixed"]


class TurnManager:
    """Manages turn order for model responses.

    Supports three strategies:
    - rotate: First responder rotates each turn, others follow in fixed order
    - confidence: Models respond in order of their confidence scores
    - fixed: Always use the same fixed order
    """

    def __init__(
        self,
        strategy: TurnStrategy = "rotate",
        fixed_order: Optional[list[str]] = None,
    ):
        """Initialize the turn manager.

        Args:
            strategy: How to determine response order
            fixed_order: Base order for 'rotate' and 'fixed' strategies
        """
        self.strategy = strategy
        self.fixed_order = fixed_order or ["claude", "gpt", "gemini", "grok"]
        self._rotation_index = 0

    @property
    def current_first_responder(self) -> str:
        """Get the current first responder for rotation strategy."""
        return self.fixed_order[self._rotation_index % len(self.fixed_order)]

    def determine_order(
        self,
        decisions: list[SpeakerDecision],
    ) -> list[str]:
        """Determine the order in which models should respond.

        Args:
            decisions: Speaker decisions from the evaluator (already sorted by confidence)

        Returns:
            Ordered list of model names that will speak
        """
        # Filter to only models that will speak
        speakers = [d.model for d in decisions if d.should_speak]

        if not speakers:
            return []

        if self.strategy == "confidence":
            # Decisions are already sorted by confidence descending
            return speakers

        elif self.strategy == "rotate":
            # Start with current first responder, maintain relative fixed order
            first = self.current_first_responder
            ordered = self._order_from_start(speakers, first)
            self.rotate_first_responder()
            return ordered

        else:  # fixed
            # Use fixed order for all speakers
            return [m for m in self.fixed_order if m in speakers]

    def _order_from_start(
        self,
        speakers: list[str],
        first: str,
    ) -> list[str]:
        """Order speakers starting from a specific model.

        Maintains the relative order from fixed_order but starts
        with the specified model.

        Args:
            speakers: Models that will speak
            first: Model to start with

        Returns:
            Reordered list of speakers
        """
        # Build order starting from 'first' in fixed_order
        speaker_set = set(speakers)

        # Find start index in fixed_order
        try:
            start_idx = self.fixed_order.index(first)
        except ValueError:
            start_idx = 0

        # Build rotated order
        rotated_fixed = (
            self.fixed_order[start_idx:] + self.fixed_order[:start_idx]
        )

        # Filter to only include speakers
        return [m for m in rotated_fixed if m in speaker_set]

    def get_first_responder(self) -> str:
        """Get the current first responder without rotating.

        Returns:
            Name of the current first responder
        """
        return self.current_first_responder

    def rotate_first_responder(self) -> None:
        """Advance to the next first responder in the rotation."""
        self._rotation_index = (self._rotation_index + 1) % len(self.fixed_order)

    def reset_rotation(self) -> None:
        """Reset rotation to the first model in fixed order."""
        self._rotation_index = 0

    def set_first_responder(self, model: str) -> None:
        """Set a specific model as the next first responder.

        Args:
            model: Model name to set as first responder
        """
        try:
            self._rotation_index = self.fixed_order.index(model)
        except ValueError:
            # Model not in fixed order, ignore
            pass

    def peek_next_first_responder(self) -> str:
        """Peek at who would be first responder after next rotation.

        Returns:
            Name of the next first responder
        """
        next_idx = (self._rotation_index + 1) % len(self.fixed_order)
        return self.fixed_order[next_idx]


def create_turn_manager(
    strategy: str = "rotate",
    fixed_order: Optional[list[str]] = None,
) -> TurnManager:
    """Factory function to create a turn manager.

    Args:
        strategy: Turn ordering strategy
        fixed_order: Custom fixed order (optional)

    Returns:
        Configured TurnManager instance
    """
    # Validate strategy
    valid_strategies: list[TurnStrategy] = ["rotate", "confidence", "fixed"]
    if strategy not in valid_strategies:
        strategy = "rotate"

    return TurnManager(
        strategy=strategy,  # type: ignore
        fixed_order=fixed_order,
    )
