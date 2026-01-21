"""Tests for the enhanced prompts system."""

import pytest

from codecrew.orchestrator.prompts import (
    MODEL_PROFILES,
    ModelProfile,
    SHOULD_SPEAK_PROMPT,
    SHOULD_SPEAK_PROMPT_V2,
    SYSTEM_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_TEMPLATE_V2,
    format_should_speak_prompt,
    format_system_prompt,
    get_model_profile,
)


class TestModelProfile:
    """Tests for the ModelProfile dataclass."""

    def test_profile_is_frozen(self):
        """ModelProfile should be immutable (frozen dataclass)."""
        profile = get_model_profile("claude")
        assert profile is not None

        with pytest.raises(AttributeError):
            profile.name = "modified"  # type: ignore

    def test_all_profiles_exist(self):
        """All expected model profiles should exist."""
        expected_models = ["claude", "gpt", "gemini", "grok"]

        for model in expected_models:
            profile = get_model_profile(model)
            assert profile is not None, f"Profile missing for {model}"
            assert profile.name == model

    def test_profile_has_required_fields(self):
        """Each profile should have all required fields populated."""
        for name, profile in MODEL_PROFILES.items():
            assert profile.name, f"{name} missing name"
            assert profile.display_name, f"{name} missing display_name"
            assert len(profile.personality_traits) > 0, f"{name} missing personality_traits"
            assert len(profile.strength_areas) > 0, f"{name} missing strength_areas"
            assert len(profile.silence_conditions) > 0, f"{name} missing silence_conditions"
            assert profile.communication_style, f"{name} missing communication_style"
            assert len(profile.response_rules) > 0, f"{name} missing response_rules"

    def test_get_model_profile_case_insensitive(self):
        """get_model_profile should be case-insensitive."""
        assert get_model_profile("claude") == get_model_profile("Claude")
        assert get_model_profile("GPT") == get_model_profile("gpt")
        assert get_model_profile("GEMINI") == get_model_profile("gemini")

    def test_get_model_profile_unknown(self):
        """get_model_profile should return None for unknown models."""
        assert get_model_profile("unknown_model") is None
        assert get_model_profile("") is None


class TestFormatShouldSpeakPrompt:
    """Tests for format_should_speak_prompt function."""

    def test_basic_format(self):
        """Basic formatting should work."""
        prompt = format_should_speak_prompt(
            model_name="claude",
            other_models=["gpt", "gemini"],
            conversation_history="User: Hello",
            user_message="How do I code?",
            use_enhanced=False,
        )

        assert "claude" in prompt
        assert "gpt" in prompt
        assert "gemini" in prompt
        assert "How do I code?" in prompt

    def test_enhanced_format_includes_strengths(self):
        """Enhanced format should include model-specific strengths."""
        prompt = format_should_speak_prompt(
            model_name="claude",
            other_models=["gpt"],
            conversation_history="",
            user_message="Test",
            use_enhanced=True,
        )

        # Should include Claude's strength areas
        assert "Complex reasoning" in prompt or "Code architecture" in prompt

    def test_enhanced_format_includes_silence_conditions(self):
        """Enhanced format should include silence conditions."""
        prompt = format_should_speak_prompt(
            model_name="gpt",
            other_models=["claude"],
            conversation_history="",
            user_message="Test",
            use_enhanced=True,
        )

        # Should include GPT's silence conditions
        assert "STAY SILENT" in prompt

    def test_previous_responses_included(self):
        """Previous responses should be included when provided."""
        prompt = format_should_speak_prompt(
            model_name="gemini",
            other_models=["claude", "gpt"],
            conversation_history="",
            user_message="Test",
            previous_responses=[("claude", "Here's my answer"), ("gpt", "I agree")],
            use_enhanced=True,
        )

        assert "Here's my answer" in prompt
        assert "I agree" in prompt

    def test_fallback_to_original_for_unknown_model(self):
        """Should fall back to original prompt for unknown models."""
        prompt = format_should_speak_prompt(
            model_name="unknown_model",
            other_models=["claude"],
            conversation_history="",
            user_message="Test",
            use_enhanced=True,
        )

        # Should use original template (no strengths section)
        assert "YOUR STRENGTHS:" not in prompt


class TestFormatSystemPrompt:
    """Tests for format_system_prompt function."""

    def test_basic_format(self):
        """Basic formatting should work."""
        prompt = format_system_prompt(
            model_name="claude",
            other_models=["gpt", "gemini"],
            use_enhanced=False,
        )

        assert "claude" in prompt.lower()
        assert "gpt" in prompt
        assert "gemini" in prompt

    def test_enhanced_format_includes_personality(self):
        """Enhanced format should include personality traits."""
        prompt = format_system_prompt(
            model_name="grok",
            other_models=["claude"],
            use_enhanced=True,
        )

        # Should include Grok's personality
        assert "YOUR PERSONALITY:" in prompt

    def test_enhanced_format_includes_response_rules(self):
        """Enhanced format should include response rules."""
        prompt = format_system_prompt(
            model_name="claude",
            other_models=["gpt"],
            use_enhanced=True,
        )

        # Should include response rules section
        assert "RESPONSE RULES" in prompt

    def test_additional_context_appended(self):
        """Additional context should be appended."""
        prompt = format_system_prompt(
            model_name="claude",
            other_models=["gpt"],
            additional_context="Custom context here",
            use_enhanced=True,
        )

        assert "Custom context here" in prompt
        assert "ADDITIONAL CONTEXT:" in prompt

    def test_tool_usage_guidelines_in_enhanced(self):
        """Enhanced prompt should include tool usage guidelines."""
        prompt = format_system_prompt(
            model_name="gpt",
            other_models=["claude"],
            use_enhanced=True,
        )

        assert "TOOL USAGE" in prompt

    def test_no_prefix_instruction(self):
        """Prompt should instruct model not to prefix responses."""
        prompt = format_system_prompt(
            model_name="gemini",
            other_models=["claude"],
            use_enhanced=True,
        )

        assert "NOT prefix" in prompt or "not prefix" in prompt.lower()


class TestPromptTemplates:
    """Tests for raw prompt templates."""

    def test_should_speak_v2_has_placeholders(self):
        """SHOULD_SPEAK_PROMPT_V2 should have all required placeholders."""
        placeholders = [
            "{model_name}",
            "{other_models}",
            "{conversation_history}",
            "{user_message}",
            "{strength_areas}",
            "{silence_conditions}",
            "{previous_responses_section}",
        ]

        for placeholder in placeholders:
            assert placeholder in SHOULD_SPEAK_PROMPT_V2, f"Missing {placeholder}"

    def test_system_prompt_v2_has_placeholders(self):
        """SYSTEM_PROMPT_TEMPLATE_V2 should have all required placeholders."""
        placeholders = [
            "{model_name}",
            "{other_models}",
            "{personality_traits}",
            "{strength_areas}",
            "{communication_style}",
            "{response_rules}",
        ]

        for placeholder in placeholders:
            assert placeholder in SYSTEM_PROMPT_TEMPLATE_V2, f"Missing {placeholder}"
