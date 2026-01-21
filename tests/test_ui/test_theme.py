"""Tests for the theme system."""

import pytest
from rich.style import Style

from codecrew.ui.theme import (
    COLORBLIND_THEME,
    DEFAULT_THEME,
    MINIMAL_THEME,
    THEMES,
    Theme,
    get_model_display_name,
    get_symbol,
    get_theme,
    list_themes,
)


class TestTheme:
    """Tests for Theme class."""

    def test_theme_has_required_attributes(self):
        """Test that themes have all required attributes."""
        theme = DEFAULT_THEME
        assert theme.name == "default"
        assert theme.description
        assert theme.model_colors
        assert theme.message_styles
        assert theme.ui_styles
        assert theme.tool_styles
        assert theme.status_styles

    def test_get_model_color(self):
        """Test getting model colors."""
        theme = DEFAULT_THEME
        assert theme.get_model_color("claude") == "orange3"
        assert theme.get_model_color("gpt") == "green"
        assert theme.get_model_color("gemini") == "blue"
        assert theme.get_model_color("grok") == "purple"

    def test_get_model_color_fallback(self):
        """Test fallback for unknown model."""
        theme = DEFAULT_THEME
        assert theme.get_model_color("unknown") == "white"

    def test_get_model_color_case_insensitive(self):
        """Test case insensitivity."""
        theme = DEFAULT_THEME
        assert theme.get_model_color("Claude") == "orange3"
        assert theme.get_model_color("CLAUDE") == "orange3"

    def test_get_model_style(self):
        """Test getting model style."""
        theme = DEFAULT_THEME
        style = theme.get_model_style("claude")
        assert isinstance(style, Style)

    def test_get_message_style(self):
        """Test getting message styles."""
        theme = DEFAULT_THEME
        user_style = theme.get_message_style("user")
        assert isinstance(user_style, Style)

    def test_get_message_style_fallback(self):
        """Test fallback for unknown role."""
        theme = DEFAULT_THEME
        style = theme.get_message_style("unknown")
        assert isinstance(style, Style)

    def test_get_ui_style(self):
        """Test getting UI styles."""
        theme = DEFAULT_THEME
        header_style = theme.get_ui_style("header")
        assert isinstance(header_style, Style)

    def test_get_tool_style(self):
        """Test getting tool styles."""
        theme = DEFAULT_THEME
        pending_style = theme.get_tool_style("pending")
        assert isinstance(pending_style, Style)

    def test_get_status_style(self):
        """Test getting status styles."""
        theme = DEFAULT_THEME
        thinking_style = theme.get_status_style("thinking")
        assert isinstance(thinking_style, Style)


class TestThemeRegistry:
    """Tests for theme registry functions."""

    def test_get_theme_default(self):
        """Test getting default theme."""
        theme = get_theme("default")
        assert theme is DEFAULT_THEME

    def test_get_theme_minimal(self):
        """Test getting minimal theme."""
        theme = get_theme("minimal")
        assert theme is MINIMAL_THEME

    def test_get_theme_colorblind(self):
        """Test getting colorblind theme."""
        theme = get_theme("colorblind")
        assert theme is COLORBLIND_THEME

    def test_get_theme_unknown_raises(self):
        """Test error on unknown theme."""
        with pytest.raises(KeyError):
            get_theme("unknown")  # type: ignore

    def test_list_themes(self):
        """Test listing available themes."""
        themes = list_themes()
        assert "default" in themes
        assert "minimal" in themes
        assert "colorblind" in themes
        assert len(themes) == 3

    def test_themes_dict_matches_list(self):
        """Test THEMES dict matches list_themes."""
        assert set(THEMES.keys()) == set(list_themes())


class TestModelDisplayNames:
    """Tests for model display name function."""

    def test_get_model_display_name_known(self):
        """Test display names for known models."""
        assert get_model_display_name("claude") == "Claude"
        assert get_model_display_name("gpt") == "GPT"
        assert get_model_display_name("gemini") == "Gemini"
        assert get_model_display_name("grok") == "Grok"

    def test_get_model_display_name_unknown(self):
        """Test display name for unknown model."""
        assert get_model_display_name("unknown") == "Unknown"

    def test_get_model_display_name_case_insensitive(self):
        """Test case insensitivity."""
        assert get_model_display_name("CLAUDE") == "Claude"
        assert get_model_display_name("Claude") == "Claude"


class TestSymbols:
    """Tests for symbol functions."""

    def test_get_symbol_unicode(self):
        """Test getting Unicode symbols."""
        assert get_symbol("thinking", use_unicode=True) == "\u2026"
        assert get_symbol("complete", use_unicode=True) == "\u2713"
        assert get_symbol("error", use_unicode=True) == "\u2717"

    def test_get_symbol_ascii(self):
        """Test getting ASCII symbols."""
        assert get_symbol("thinking", use_unicode=False) == "..."
        assert get_symbol("complete", use_unicode=False) == "[OK]"
        assert get_symbol("error", use_unicode=False) == "[X]"

    def test_get_symbol_unknown(self):
        """Test getting unknown symbol returns empty."""
        assert get_symbol("unknown") == ""
        assert get_symbol("unknown", use_unicode=False) == ""


class TestThemeConsistency:
    """Tests for consistency across themes."""

    @pytest.mark.parametrize("theme_name", ["default", "minimal", "colorblind"])
    def test_all_themes_have_model_colors(self, theme_name: str):
        """Test all themes have colors for all models."""
        theme = get_theme(theme_name)  # type: ignore
        for model in ["claude", "gpt", "gemini", "grok", "user", "system"]:
            assert model in theme.model_colors

    @pytest.mark.parametrize("theme_name", ["default", "minimal", "colorblind"])
    def test_all_themes_have_message_styles(self, theme_name: str):
        """Test all themes have styles for all message types."""
        theme = get_theme(theme_name)  # type: ignore
        for role in ["user", "assistant", "system", "error"]:
            assert role in theme.message_styles

    @pytest.mark.parametrize("theme_name", ["default", "minimal", "colorblind"])
    def test_all_themes_have_tool_styles(self, theme_name: str):
        """Test all themes have tool styles."""
        theme = get_theme(theme_name)  # type: ignore
        for status in ["pending", "executing", "success", "error"]:
            assert status in theme.tool_styles

    @pytest.mark.parametrize("theme_name", ["default", "minimal", "colorblind"])
    def test_all_themes_have_status_styles(self, theme_name: str):
        """Test all themes have status styles."""
        theme = get_theme(theme_name)  # type: ignore
        for status in ["thinking", "streaming", "idle", "error"]:
            assert status in theme.status_styles
