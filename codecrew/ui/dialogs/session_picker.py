"""Session picker dialog for selecting saved sessions."""

from dataclasses import dataclass
from typing import Any, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codecrew.ui.theme import Theme


class SessionCompleter(Completer):
    """Completer for session IDs and names."""

    def __init__(self, sessions: list[dict[str, Any]]):
        """Initialize with session list.

        Args:
            sessions: List of session dictionaries
        """
        self.sessions = sessions

    def get_completions(self, document, complete_event):
        """Get completions for session input.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects
        """
        text = document.text_before_cursor.lower()

        for session in self.sessions:
            session_id = session.get("id", "")
            session_name = session.get("name", "")

            # Match against ID or name
            if session_id.lower().startswith(text) or (
                session_name and session_name.lower().startswith(text)
            ):
                display = f"{session_id[:8]}... - {session_name or 'Unnamed'}"
                yield Completion(
                    session_id,
                    start_position=-len(text),
                    display=display,
                )


@dataclass
class SessionPicker:
    """Dialog for picking a session from a list.

    Displays available sessions in a table and allows
    selection by ID, number, or name search.
    """

    console: Console
    theme: Theme

    async def show(
        self,
        sessions: list[dict[str, Any]],
        title: str = "Select Session",
        allow_new: bool = True,
    ) -> Optional[str]:
        """Show the session picker and get user selection.

        Args:
            sessions: List of session dictionaries
            title: Dialog title
            allow_new: Whether to allow creating a new session

        Returns:
            Selected session ID, "new" for new session, or None if cancelled
        """
        if not sessions and not allow_new:
            self.console.print("[yellow]No sessions available[/yellow]")
            return None

        # Display session table
        self._display_sessions(sessions, title, allow_new)

        # Get user input
        return await self._get_selection(sessions, allow_new)

    def _display_sessions(
        self,
        sessions: list[dict[str, Any]],
        title: str,
        allow_new: bool,
    ) -> None:
        """Display the sessions table.

        Args:
            sessions: List of sessions
            title: Table title
            allow_new: Whether new session option is available
        """
        table = Table(title=title, show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Name", style="green")
        table.add_column("Updated", style="yellow", width=18)

        for i, session in enumerate(sessions, 1):
            session_id = session.get("id", "")[:8] + "..."
            name = session.get("name", "") or "[dim]Unnamed[/dim]"
            updated = session.get("updated_at", "")[:16] if session.get("updated_at") else "-"

            table.add_row(str(i), session_id, name, updated)

        self.console.print()
        self.console.print(table)

        # Show options
        options = Text()
        options.append("\nEnter: ", style="dim")
        options.append("number", style="cyan")
        options.append(" or ", style="dim")
        options.append("session ID", style="cyan")

        if allow_new:
            options.append(" | ", style="dim")
            options.append("'new'", style="green")
            options.append(" for new session", style="dim")

        options.append(" | ", style="dim")
        options.append("'q'", style="red")
        options.append(" to cancel", style="dim")

        self.console.print(options)

    async def _get_selection(
        self,
        sessions: list[dict[str, Any]],
        allow_new: bool,
    ) -> Optional[str]:
        """Get user selection.

        Args:
            sessions: List of sessions
            allow_new: Whether new session is allowed

        Returns:
            Session ID, "new", or None
        """
        completer = SessionCompleter(sessions)
        session_prompt = PromptSession(completer=completer)

        while True:
            try:
                response = await session_prompt.prompt_async("Select: ")
                response = response.strip()

                if not response or response.lower() in ("q", "quit", "cancel"):
                    return None

                if allow_new and response.lower() == "new":
                    return "new"

                # Try as number
                try:
                    num = int(response)
                    if 1 <= num <= len(sessions):
                        return sessions[num - 1].get("id")
                    else:
                        self.console.print(f"[red]Invalid number: {num}[/red]")
                        continue
                except ValueError:
                    pass

                # Try as session ID (partial match)
                matches = [
                    s for s in sessions
                    if s.get("id", "").startswith(response)
                ]

                if len(matches) == 1:
                    return matches[0].get("id")
                elif len(matches) > 1:
                    self.console.print(
                        f"[yellow]Multiple matches. Be more specific.[/yellow]"
                    )
                    continue
                else:
                    # Try name match
                    name_matches = [
                        s for s in sessions
                        if s.get("name", "").lower().startswith(response.lower())
                    ]
                    if len(name_matches) == 1:
                        return name_matches[0].get("id")
                    elif len(name_matches) > 1:
                        self.console.print(
                            f"[yellow]Multiple matches. Be more specific.[/yellow]"
                        )
                        continue

                self.console.print(f"[red]Session not found: {response}[/red]")

            except (EOFError, KeyboardInterrupt):
                return None


class ConfirmationDialog:
    """Simple yes/no confirmation dialog."""

    def __init__(self, console: Console, theme: Theme):
        """Initialize the dialog.

        Args:
            console: Rich console
            theme: Theme for styling
        """
        self.console = console
        self.theme = theme

    async def confirm(
        self,
        message: str,
        default: bool = True,
        danger: bool = False,
    ) -> bool:
        """Show confirmation prompt.

        Args:
            message: Confirmation message
            default: Default value if empty input
            danger: Whether this is a dangerous action

        Returns:
            True for yes, False for no
        """
        prompt_text = Text()
        prompt_text.append(message)
        prompt_text.append(" ")

        if default:
            prompt_text.append("[Y/n]", style="green" if not danger else "yellow")
        else:
            prompt_text.append("[y/N]", style="red" if danger else "dim")

        prompt_text.append(": ")

        self.console.print(prompt_text, end="")

        session = PromptSession()
        try:
            response = await session.prompt_async("")
            response = response.strip().lower()

            if not response:
                return default
            return response in ("y", "yes")

        except (EOFError, KeyboardInterrupt):
            return False


class TextInputDialog:
    """Simple text input dialog."""

    def __init__(self, console: Console, theme: Theme):
        """Initialize the dialog.

        Args:
            console: Rich console
            theme: Theme for styling
        """
        self.console = console
        self.theme = theme

    async def prompt(
        self,
        message: str,
        default: str = "",
        required: bool = False,
    ) -> Optional[str]:
        """Show text input prompt.

        Args:
            message: Prompt message
            default: Default value
            required: Whether input is required

        Returns:
            User input or None if cancelled
        """
        prompt_text = Text()
        prompt_text.append(message)

        if default:
            prompt_text.append(f" [{default}]", style="dim")

        prompt_text.append(": ")

        self.console.print(prompt_text, end="")

        session = PromptSession()

        while True:
            try:
                response = await session.prompt_async("")
                response = response.strip()

                if not response:
                    if default:
                        return default
                    elif required:
                        self.console.print("[yellow]Input required[/yellow]")
                        continue
                    else:
                        return None

                return response

            except (EOFError, KeyboardInterrupt):
                return None
