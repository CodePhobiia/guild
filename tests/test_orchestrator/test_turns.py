"""Tests for turn management."""

import pytest

from codecrew.orchestrator.events import SpeakerDecision
from codecrew.orchestrator.turns import TurnManager, create_turn_manager


class TestTurnManager:
    """Tests for TurnManager class."""

    def test_default_fixed_order(self) -> None:
        """Test default fixed order."""
        tm = TurnManager()
        assert tm.fixed_order == ["claude", "gpt", "gemini", "grok"]

    def test_custom_fixed_order(self) -> None:
        """Test custom fixed order."""
        tm = TurnManager(fixed_order=["gpt", "claude"])
        assert tm.fixed_order == ["gpt", "claude"]

    def test_current_first_responder(self) -> None:
        """Test getting current first responder."""
        tm = TurnManager(fixed_order=["claude", "gpt", "gemini"])
        assert tm.current_first_responder == "claude"

    def test_rotate_first_responder(self) -> None:
        """Test rotating first responder."""
        tm = TurnManager(fixed_order=["claude", "gpt", "gemini"])

        assert tm.current_first_responder == "claude"
        tm.rotate_first_responder()
        assert tm.current_first_responder == "gpt"
        tm.rotate_first_responder()
        assert tm.current_first_responder == "gemini"
        tm.rotate_first_responder()
        assert tm.current_first_responder == "claude"  # Wraps around

    def test_reset_rotation(self) -> None:
        """Test resetting rotation."""
        tm = TurnManager(fixed_order=["claude", "gpt", "gemini"])
        tm.rotate_first_responder()
        tm.rotate_first_responder()
        assert tm.current_first_responder == "gemini"

        tm.reset_rotation()
        assert tm.current_first_responder == "claude"

    def test_set_first_responder(self) -> None:
        """Test setting a specific first responder."""
        tm = TurnManager(fixed_order=["claude", "gpt", "gemini"])
        tm.set_first_responder("gemini")
        assert tm.current_first_responder == "gemini"

    def test_set_first_responder_unknown_model(self) -> None:
        """Test setting unknown model as first responder (no-op)."""
        tm = TurnManager(fixed_order=["claude", "gpt"])
        tm.set_first_responder("unknown")
        assert tm.current_first_responder == "claude"  # Unchanged


class TestDetermineOrder:
    """Tests for determine_order method."""

    def test_confidence_strategy(self) -> None:
        """Test ordering by confidence."""
        tm = TurnManager(strategy="confidence")

        decisions = [
            SpeakerDecision.speak("claude", 0.7, "reason"),
            SpeakerDecision.speak("gpt", 0.9, "reason"),
            SpeakerDecision.speak("gemini", 0.5, "reason"),
        ]

        # Decisions should already be sorted by confidence
        # so the order should match
        order = tm.determine_order(decisions)
        assert order == ["claude", "gpt", "gemini"]

    def test_fixed_strategy(self) -> None:
        """Test fixed ordering."""
        tm = TurnManager(strategy="fixed", fixed_order=["claude", "gpt", "gemini", "grok"])

        decisions = [
            SpeakerDecision.speak("gpt", 0.9, "reason"),
            SpeakerDecision.speak("claude", 0.7, "reason"),
            SpeakerDecision.speak("grok", 0.5, "reason"),
        ]

        order = tm.determine_order(decisions)
        assert order == ["claude", "gpt", "grok"]  # Fixed order, gemini excluded

    def test_rotate_strategy(self) -> None:
        """Test rotating first responder."""
        tm = TurnManager(strategy="rotate", fixed_order=["claude", "gpt", "gemini"])

        decisions = [
            SpeakerDecision.speak("claude", 0.7, "reason"),
            SpeakerDecision.speak("gpt", 0.8, "reason"),
            SpeakerDecision.speak("gemini", 0.6, "reason"),
        ]

        # First turn: claude first
        order1 = tm.determine_order(decisions)
        assert order1[0] == "claude"

        # Second turn: gpt first (rotated)
        order2 = tm.determine_order(decisions)
        assert order2[0] == "gpt"

        # Third turn: gemini first
        order3 = tm.determine_order(decisions)
        assert order3[0] == "gemini"

    def test_silent_models_excluded(self) -> None:
        """Test that silent models are excluded from order."""
        tm = TurnManager(strategy="fixed", fixed_order=["claude", "gpt", "gemini"])

        decisions = [
            SpeakerDecision.speak("claude", 0.8, "reason"),
            SpeakerDecision.silent("gpt", 0.2, "nothing to add"),
            SpeakerDecision.speak("gemini", 0.7, "reason"),
        ]

        order = tm.determine_order(decisions)
        assert "gpt" not in order
        assert order == ["claude", "gemini"]

    def test_empty_decisions(self) -> None:
        """Test with no decisions."""
        tm = TurnManager()
        order = tm.determine_order([])
        assert order == []

    def test_all_silent(self) -> None:
        """Test when all models are silent."""
        tm = TurnManager()

        decisions = [
            SpeakerDecision.silent("claude", 0.2, "nothing to add"),
            SpeakerDecision.silent("gpt", 0.1, "already covered"),
        ]

        order = tm.determine_order(decisions)
        assert order == []


class TestCreateTurnManager:
    """Tests for create_turn_manager factory."""

    def test_create_with_defaults(self) -> None:
        """Test creating with defaults."""
        tm = create_turn_manager()
        assert tm.strategy == "rotate"

    def test_create_with_strategy(self) -> None:
        """Test creating with specific strategy."""
        tm = create_turn_manager(strategy="confidence")
        assert tm.strategy == "confidence"

    def test_create_with_invalid_strategy(self) -> None:
        """Test that invalid strategy falls back to rotate."""
        tm = create_turn_manager(strategy="invalid")
        assert tm.strategy == "rotate"

    def test_create_with_custom_order(self) -> None:
        """Test creating with custom order."""
        tm = create_turn_manager(fixed_order=["gpt", "claude"])
        assert tm.fixed_order == ["gpt", "claude"]
