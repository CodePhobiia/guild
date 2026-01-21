"""Input area component with @mention and command completion."""

import asyncio
from typing import Callable, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.text import Text

from codecrew.ui.theme import Theme, get_model_display_name


class MentionCompleter(Completer):
    """Completer for @mentions and /commands.

    Provides context-aware completions:
    - @model mentions (@claude, @gpt, @gemini, @grok, @all)
    - /commands (/help, /quit, /clear, etc.)
    """

    def __init__(
        self,
        models: list[str],
        commands: list[tuple[str, str]],  # (command, description)
    ):
        """Initialize the completer.

        Args:
            models: List of available model names
            commands: List of (command, description) tuples
        """
        self.models = models
        self.commands = commands

        # Build mention list
        self.mentions = [f"@{m}" for m in models] + ["@all"]

    def get_completions(self, document, complete_event):
        """Get completions for the current input.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects
        """
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        # Handle @mentions
        if "@" in text:
            # Find the last @ and check if we're completing after it
            last_at = text.rfind("@")
            if last_at >= 0:
                partial = text[last_at:]
                for mention in self.mentions:
                    if mention.startswith(partial.lower()):
                        # Calculate start position
                        start_pos = -len(partial)
                        display = f"{mention} ({get_model_display_name(mention[1:])})"
                        yield Completion(
                            mention,
                            start_position=start_pos,
                            display=display,
                        )

        # Handle /commands at start of line
        elif text.startswith("/"):
            partial = text.lower()
            for cmd, desc in self.commands:
                if cmd.startswith(partial):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd} - {desc}",
                        display_meta=desc,
                    )


# Default slash commands
DEFAULT_COMMANDS = [
    ("/help", "Show help and available commands"),
    ("/quit", "Exit CodeCrew"),
    ("/exit", "Exit CodeCrew"),
    ("/clear", "Clear the screen"),
    ("/new", "Start a new session"),
    ("/sessions", "List saved sessions"),
    ("/load", "Load a session by ID"),
    ("/save", "Save current session"),
    ("/export", "Export current session"),
    ("/pin", "Pin a message"),
    ("/unpin", "Unpin a message"),
    ("/stats", "Show conversation statistics"),
    ("/models", "Show model status"),
    ("/config", "Show current configuration"),
    ("/theme", "Change color theme"),
    ("/compact", "Toggle compact mode"),
]


class InputArea:
    """Input area with @mention completion and command handling.

    Uses prompt_toolkit for advanced input features:
    - Multi-line input
    - @mention autocomplete
    - Command completion
    - History navigation
    - Keyboard shortcuts
    """

    def __init__(
        self,
        theme: Theme,
        models: list[str],
        commands: Optional[list[tuple[str, str]]] = None,
        multiline: bool = True,
        history_size: int = 100,
    ):
        """Initialize the input area.

        Args:
            theme: Theme for styling
            models: List of available model names
            commands: List of (command, description) tuples
            multiline: Enable multi-line input
            history_size: Maximum history entries
        """
        self.theme = theme
        self.models = models
        self.commands = commands or DEFAULT_COMMANDS
        self.multiline = multiline

        # Create completer
        self.completer = MentionCompleter(models, self.commands)

        # Create history
        self.history = InMemoryHistory()

        # Create key bindings
        self.key_bindings = self._create_key_bindings()

        # Create prompt style
        self.prompt_style = self._create_prompt_style()

        # Create prompt session
        self.session: Optional[PromptSession] = None

        # Callbacks
        self._on_submit: Optional[Callable[[str], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the input area.

        Returns:
            KeyBindings instance
        """
        kb = KeyBindings()

        @kb.add("c-c")
        def handle_ctrl_c(event):
            """Handle Ctrl+C to cancel current input."""
            event.current_buffer.reset()
            if self._on_cancel:
                self._on_cancel()

        @kb.add("c-d")
        def handle_ctrl_d(event):
            """Handle Ctrl+D to exit."""
            raise EOFError

        if self.multiline:
            @kb.add("escape", "enter")
            def handle_alt_enter(event):
                """Handle Alt+Enter to insert newline in multiline mode."""
                event.current_buffer.insert_text("\n")

            @kb.add("enter")
            def handle_enter(event):
                """Handle Enter to submit."""
                buffer = event.current_buffer
                text = buffer.text

                # Submit if not empty
                if text.strip():
                    buffer.validate_and_handle()
                else:
                    # Insert newline if empty
                    buffer.insert_text("\n")

        return kb

    def _create_prompt_style(self) -> PTStyle:
        """Create prompt_toolkit style from theme.

        Returns:
            PTStyle instance
        """
        # Map Rich color names to prompt_toolkit compatible colors
        # prompt_toolkit uses ANSI color names or hex codes
        color_map = {
            "orange3": "#d75f00",  # Rich orange3 -> hex
            "green": "ansigreen",
            "blue": "ansiblue",
            "purple": "ansipurple",
            "bright_white": "ansibrightwhite",
            "grey50": "ansigray",
            "yellow": "ansiyellow",
        }

        # Get colors from theme and convert to prompt_toolkit compatible
        model_colors = {}
        for m in self.models:
            rich_color = self.theme.get_model_color(m)
            model_colors[m] = color_map.get(rich_color, rich_color)

        # Build style dictionary
        style_dict = {
            "prompt": "bold cyan",
            "": "white",  # Default text
        }

        # Add model colors for completions
        for model, color in model_colors.items():
            style_dict[f"completion-menu.completion.{model}"] = color

        return PTStyle.from_dict(style_dict)

    def _get_prompt(self) -> HTML:
        """Get the prompt string.

        Returns:
            Formatted prompt
        """
        if self.multiline:
            return HTML("<prompt>>>> </prompt><hint>(Alt+Enter for newline)</hint>\n")
        return HTML("<prompt>>>> </prompt>")

    def on_submit(self, callback: Callable[[str], None]) -> None:
        """Set callback for input submission.

        Args:
            callback: Function called with submitted text
        """
        self._on_submit = callback

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """Set callback for input cancellation.

        Args:
            callback: Function called when input is cancelled
        """
        self._on_cancel = callback

    async def prompt_async(self, default: str = "") -> str:
        """Get input asynchronously.

        Args:
            default: Default input text

        Returns:
            User input string

        Raises:
            EOFError: If Ctrl+D is pressed
            KeyboardInterrupt: If Ctrl+C is pressed
        """
        if self.session is None:
            self.session = PromptSession(
                completer=self.completer,
                history=self.history,
                key_bindings=self.key_bindings,
                style=self.prompt_style,
                auto_suggest=AutoSuggestFromHistory(),
                multiline=self.multiline,
                prompt_continuation="... ",
            )

        return await self.session.prompt_async(
            self._get_prompt(),
            default=default,
        )

    def prompt(self, default: str = "") -> str:
        """Get input synchronously.

        Args:
            default: Default input text

        Returns:
            User input string

        Raises:
            EOFError: If Ctrl+D is pressed
            KeyboardInterrupt: If Ctrl+C is pressed
        """
        return asyncio.get_event_loop().run_until_complete(
            self.prompt_async(default)
        )

    def add_to_history(self, text: str) -> None:
        """Add text to input history.

        Args:
            text: Text to add to history
        """
        self.history.append_string(text)


class SimpleInput:
    """Simple input for permission dialogs and confirmations.

    Uses basic prompt_toolkit without complex completions.
    """

    def __init__(
        self,
        theme: Theme,
        prompt_text: str = "> ",
    ):
        """Initialize simple input.

        Args:
            theme: Theme for styling
            prompt_text: Prompt string to display
        """
        self.theme = theme
        self.prompt_text = prompt_text
        self.session = PromptSession()

    async def prompt_async(
        self,
        prompt: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> str:
        """Get input asynchronously.

        Args:
            prompt: Override prompt text
            validator: Optional validation function

        Returns:
            User input string
        """
        text = prompt or self.prompt_text
        while True:
            result = await self.session.prompt_async(text)
            if validator is None or validator(result):
                return result

    async def confirm_async(
        self,
        prompt: str = "Continue? [Y/n] ",
        default: bool = True,
    ) -> bool:
        """Get yes/no confirmation.

        Args:
            prompt: Confirmation prompt
            default: Default value if empty input

        Returns:
            True for yes, False for no
        """
        result = await self.prompt_async(prompt)
        if not result.strip():
            return default
        return result.strip().lower() in ("y", "yes", "true", "1")

    async def choice_async(
        self,
        prompt: str,
        choices: list[str],
        default: Optional[str] = None,
    ) -> str:
        """Get choice from list.

        Args:
            prompt: Choice prompt
            choices: Valid choices
            default: Default choice if empty input

        Returns:
            Selected choice
        """
        choices_lower = [c.lower() for c in choices]

        def validator(text: str) -> bool:
            if not text.strip() and default:
                return True
            return text.strip().lower() in choices_lower

        result = await self.prompt_async(prompt, validator)
        if not result.strip() and default:
            return default
        return result.strip()


def render_input_hint(theme: Theme, use_unicode: bool = True) -> Text:
    """Render input hints.

    Args:
        theme: Theme for styling
        use_unicode: Whether to use Unicode characters

    Returns:
        Text with input hints
    """
    text = Text()
    text.append("Type your message", style="dim")
    text.append(" | ", style="dim")
    text.append("@model", style="cyan")
    text.append(" to mention", style="dim")
    text.append(" | ", style="dim")
    text.append("/help", style="cyan")
    text.append(" for commands", style="dim")
    return text
