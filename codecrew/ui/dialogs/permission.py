"""Permission dialog for tool execution approval."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from codecrew.models.types import ToolCall
from codecrew.ui.theme import Theme, get_model_display_name, get_symbol


class PermissionResponse(Enum):
    """User response to permission request."""

    ALLOW = "allow"  # Allow this execution
    DENY = "deny"  # Deny this execution
    ALWAYS = "always"  # Always allow this tool
    NEVER = "never"  # Never allow this tool
    ALLOW_SESSION = "allow_session"  # Allow for this session


@dataclass
class PermissionDialog:
    """Dialog for requesting tool execution permission.

    Displays tool call details and prompts for user decision.
    Supports:
    - [Y]es - Allow this execution
    - [N]o - Deny this execution
    - [A]lways - Always allow this tool
    - [S]ession - Allow for this session
    - [Never] - Never allow this tool
    """

    theme: Theme
    console: Console
    use_unicode: bool = True

    async def show(
        self,
        model: str,
        tool_call: ToolCall,
        permission_level: str,
        reason: Optional[str] = None,
    ) -> PermissionResponse:
        """Show the permission dialog and get user response.

        Args:
            model: Model requesting the tool
            tool_call: The tool call details
            permission_level: Permission level (safe, cautious, dangerous)
            reason: Optional reason for the request

        Returns:
            User's permission response
        """
        # Build the dialog content
        content = Text()

        # Warning icon and title
        content.append(get_symbol("warning", self.use_unicode), style="yellow bold")
        content.append(" ")
        content.append("Permission Required\n\n", style="bold")

        # Tool info
        content.append("Tool: ", style="dim")
        content.append(tool_call.name, style="bold yellow")
        content.append("\n")

        # Permission level with color
        content.append("Level: ", style="dim")
        if permission_level.lower() == "dangerous":
            content.append("DANGEROUS", style="red bold")
            content.append(" - This operation could modify files or system state\n", style="dim")
        elif permission_level.lower() == "cautious":
            content.append("CAUTIOUS", style="yellow")
            content.append(" - This operation may have side effects\n", style="dim")
        else:
            content.append(permission_level.upper(), style="green")
            content.append("\n")

        # Model attribution
        content.append("\nRequested by: ", style="dim")
        model_style = self.theme.get_model_style(model)
        content.append(get_model_display_name(model), style=model_style)
        content.append("\n")

        # Arguments
        if tool_call.arguments:
            content.append("\nArguments:\n", style="dim")
            for key, value in tool_call.arguments.items():
                content.append(f"  {key}: ", style="cyan")
                str_value = str(value)
                # Truncate very long values
                if len(str_value) > 80:
                    str_value = str_value[:77] + "..."
                # Handle multi-line values
                if "\n" in str_value:
                    lines = str_value.split("\n")
                    if len(lines) > 3:
                        str_value = "\n".join(lines[:3]) + "\n    ..."
                content.append(f"{str_value}\n")

        # Reason if provided
        if reason:
            content.append(f"\nReason: {reason}\n", style="dim italic")

        # Options
        content.append("\n")
        content.append("[Y]", style="green bold")
        content.append("es  ", style="dim")
        content.append("[N]", style="red bold")
        content.append("o  ", style="dim")
        content.append("[A]", style="cyan bold")
        content.append("lways  ", style="dim")
        content.append("[S]", style="blue bold")
        content.append("ession  ", style="dim")
        content.append("[", style="dim")
        content.append("Never", style="magenta bold")
        content.append("]", style="dim")

        # Display the panel
        self.console.print()
        self.console.print(Panel(
            content,
            title="Tool Permission Request",
            title_align="left",
            border_style="yellow",
            padding=(1, 2),
        ))

        # Get user input
        return await self._get_response()

    async def _get_response(self) -> PermissionResponse:
        """Get user response from input.

        Returns:
            PermissionResponse based on user input
        """
        session = PromptSession()

        while True:
            try:
                response = await session.prompt_async(
                    "Your choice: ",
                )
                response = response.strip().lower()

                if response in ("y", "yes"):
                    return PermissionResponse.ALLOW
                elif response in ("n", "no"):
                    return PermissionResponse.DENY
                elif response in ("a", "always"):
                    return PermissionResponse.ALWAYS
                elif response in ("s", "session"):
                    return PermissionResponse.ALLOW_SESSION
                elif response == "never":
                    return PermissionResponse.NEVER
                else:
                    self.console.print(
                        "[yellow]Please enter Y, N, A, S, or Never[/yellow]"
                    )

            except (EOFError, KeyboardInterrupt):
                return PermissionResponse.DENY

    def show_sync(
        self,
        model: str,
        tool_call: ToolCall,
        permission_level: str,
        reason: Optional[str] = None,
    ) -> PermissionResponse:
        """Show the permission dialog synchronously.

        Args:
            model: Model requesting the tool
            tool_call: The tool call details
            permission_level: Permission level
            reason: Optional reason

        Returns:
            User's permission response
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.show(model, tool_call, permission_level, reason)
        )


class QuickPermissionPrompt:
    """Quick inline permission prompt for simple confirmations."""

    def __init__(self, console: Console, theme: Theme):
        """Initialize the prompt.

        Args:
            console: Rich console
            theme: Theme for styling
        """
        self.console = console
        self.theme = theme

    async def confirm(
        self,
        tool_name: str,
        model: str,
        action: str = "execute",
    ) -> bool:
        """Quick confirmation for tool execution.

        Args:
            tool_name: Name of the tool
            model: Model requesting
            action: Action description

        Returns:
            True to allow, False to deny
        """
        text = Text()
        model_style = self.theme.get_model_style(model)

        text.append(get_model_display_name(model), style=model_style)
        text.append(f" wants to {action} ")
        text.append(tool_name, style="yellow bold")
        text.append(" [Y/n]: ")

        self.console.print(text, end="")

        session = PromptSession()
        try:
            response = await session.prompt_async("")
            return response.strip().lower() in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False


class DangerousOperationWarning:
    """Warning display for dangerous operations."""

    def __init__(self, console: Console, theme: Theme, use_unicode: bool = True):
        """Initialize the warning display.

        Args:
            console: Rich console
            theme: Theme for styling
            use_unicode: Whether to use Unicode
        """
        self.console = console
        self.theme = theme
        self.use_unicode = use_unicode

    def show(
        self,
        operation: str,
        details: str,
        consequences: list[str],
    ) -> None:
        """Display a dangerous operation warning.

        Args:
            operation: Operation name
            details: Operation details
            consequences: List of potential consequences
        """
        content = Text()

        # Warning header
        content.append(get_symbol("warning", self.use_unicode), style="red bold")
        content.append(" ")
        content.append("DANGEROUS OPERATION\n\n", style="red bold")

        # Operation
        content.append("Operation: ", style="dim")
        content.append(f"{operation}\n", style="bold")

        # Details
        content.append("Details: ", style="dim")
        content.append(f"{details}\n\n", style="white")

        # Consequences
        if consequences:
            content.append("Potential consequences:\n", style="yellow")
            for consequence in consequences:
                content.append(f"  • {consequence}\n", style="yellow")

        self.console.print(Panel(
            content,
            title="[red bold]Warning[/red bold]",
            border_style="red",
            padding=(1, 2),
        ))
