"""Slash command handlers for the TUI."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from codecrew.ui.app import ChatApp


# Command categories for organized help display
COMMAND_GROUPS: dict[str, list[str]] = {
    "Session": ["/new", "/sessions", "/load", "/save", "/export"],
    "Display": ["/clear", "/compact", "/decisions", "/theme"],
    "Navigation": ["/search", "/goto", "/history"],
    "Information": ["/help", "/models", "/config", "/stats", "/keys"],
    "Messages": ["/pin", "/unpin", "/copy"],
    "Git": ["/git", "/status", "/diff", "/log", "/branch"],
    "System": ["/quit"],
}


class CommandResult(Enum):
    """Result of command execution."""

    SUCCESS = "success"
    ERROR = "error"
    EXIT = "exit"
    CONTINUE = "continue"  # Command handled, continue normal flow


@dataclass
class Command:
    """A slash command definition."""

    name: str
    aliases: list[str]
    description: str
    usage: str
    handler: Callable
    category: str = "Other"
    min_args: int = 0
    max_args: Optional[int] = None

    def matches(self, text: str) -> bool:
        """Check if text matches this command.

        Args:
            text: Command text (e.g., "/help", "/quit")

        Returns:
            True if matches
        """
        cmd = text.lower().split()[0] if text else ""
        return cmd == self.name or cmd in self.aliases


class CommandHandler:
    """Handles slash commands in the TUI.

    Provides commands for:
    - Help and information
    - Session management
    - Display control
    - Configuration
    """

    def __init__(self, app: "ChatApp"):
        """Initialize command handler.

        Args:
            app: Parent ChatApp instance
        """
        self.app = app
        self.console = Console()
        self._commands: dict[str, Command] = {}
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register the default commands."""
        commands = [
            # Information
            Command(
                name="/help",
                aliases=["/h", "/?"],
                description="Show help and available commands",
                usage="/help [command]",
                handler=self._cmd_help,
                category="Information",
                max_args=1,
            ),
            Command(
                name="/stats",
                aliases=["/info"],
                description="Show conversation statistics",
                usage="/stats",
                handler=self._cmd_stats,
                category="Information",
            ),
            Command(
                name="/models",
                aliases=[],
                description="Show model status",
                usage="/models",
                handler=self._cmd_models,
                category="Information",
            ),
            Command(
                name="/config",
                aliases=["/settings"],
                description="Show current configuration",
                usage="/config",
                handler=self._cmd_config,
                category="Information",
            ),
            Command(
                name="/keys",
                aliases=["/shortcuts", "/bindings"],
                description="Show keyboard shortcuts",
                usage="/keys",
                handler=self._cmd_keys,
                category="Information",
            ),
            # System
            Command(
                name="/quit",
                aliases=["/exit", "/q"],
                description="Exit CodeCrew",
                usage="/quit",
                handler=self._cmd_quit,
                category="System",
            ),
            # Display
            Command(
                name="/clear",
                aliases=["/cls"],
                description="Clear the screen",
                usage="/clear",
                handler=self._cmd_clear,
                category="Display",
            ),
            Command(
                name="/theme",
                aliases=[],
                description="Change color theme",
                usage="/theme [name]",
                handler=self._cmd_theme,
                category="Display",
                max_args=1,
            ),
            Command(
                name="/compact",
                aliases=["/mini"],
                description="Toggle compact mode",
                usage="/compact",
                handler=self._cmd_compact,
                category="Display",
            ),
            Command(
                name="/decisions",
                aliases=["/verbose"],
                description="Toggle showing model decisions",
                usage="/decisions",
                handler=self._cmd_decisions,
                category="Display",
            ),
            # Session
            Command(
                name="/new",
                aliases=[],
                description="Start a new session",
                usage="/new [name]",
                handler=self._cmd_new,
                category="Session",
                max_args=1,
            ),
            Command(
                name="/sessions",
                aliases=["/ls"],
                description="List saved sessions",
                usage="/sessions [limit]",
                handler=self._cmd_sessions,
                category="Session",
                max_args=1,
            ),
            Command(
                name="/load",
                aliases=["/open"],
                description="Load a session by ID",
                usage="/load <session_id>",
                handler=self._cmd_load,
                category="Session",
                min_args=1,
                max_args=1,
            ),
            Command(
                name="/save",
                aliases=[],
                description="Save current session",
                usage="/save [name]",
                handler=self._cmd_save,
                category="Session",
                max_args=1,
            ),
            Command(
                name="/export",
                aliases=[],
                description="Export current session",
                usage="/export [format]",
                handler=self._cmd_export,
                category="Session",
                max_args=1,
            ),
            # Messages
            Command(
                name="/pin",
                aliases=[],
                description="Pin a message by number",
                usage="/pin <message_number>",
                handler=self._cmd_pin,
                category="Messages",
                min_args=1,
                max_args=1,
            ),
            Command(
                name="/unpin",
                aliases=[],
                description="Unpin a message by number",
                usage="/unpin <message_number>",
                handler=self._cmd_unpin,
                category="Messages",
                min_args=1,
                max_args=1,
            ),
            Command(
                name="/copy",
                aliases=["/cp"],
                description="Copy message to clipboard",
                usage="/copy [message_number]",
                handler=self._cmd_copy,
                category="Messages",
                max_args=1,
            ),
            # Navigation
            Command(
                name="/search",
                aliases=["/find", "/s"],
                description="Search messages",
                usage="/search <query>",
                handler=self._cmd_search,
                category="Navigation",
                min_args=1,
            ),
            Command(
                name="/goto",
                aliases=["/g", "/jump"],
                description="Jump to message",
                usage="/goto <message_number|message_id>",
                handler=self._cmd_goto,
                category="Navigation",
                min_args=1,
                max_args=1,
            ),
            Command(
                name="/history",
                aliases=["/hist"],
                description="Show input history",
                usage="/history [limit]",
                handler=self._cmd_history,
                category="Navigation",
                max_args=1,
            ),
            # Git
            Command(
                name="/git",
                aliases=[],
                description="Git operations overview",
                usage="/git",
                handler=self._cmd_git,
                category="Git",
            ),
            Command(
                name="/status",
                aliases=["/st"],
                description="Show git status",
                usage="/status",
                handler=self._cmd_status,
                category="Git",
            ),
            Command(
                name="/diff",
                aliases=[],
                description="Show git diff",
                usage="/diff [--staged] [file]",
                handler=self._cmd_diff,
                category="Git",
                max_args=2,
            ),
            Command(
                name="/log",
                aliases=["/commits"],
                description="Show recent commits",
                usage="/log [limit]",
                handler=self._cmd_log,
                category="Git",
                max_args=1,
            ),
            Command(
                name="/branch",
                aliases=["/br"],
                description="Show or manage branches",
                usage="/branch [name]",
                handler=self._cmd_branch,
                category="Git",
                max_args=1,
            ),
        ]

        for cmd in commands:
            self._commands[cmd.name] = cmd
            for alias in cmd.aliases:
                self._commands[alias] = cmd

    def is_command(self, text: str) -> bool:
        """Check if text is a command.

        Args:
            text: Input text

        Returns:
            True if text starts with /
        """
        return text.strip().startswith("/")

    def parse_command(self, text: str) -> tuple[str, list[str]]:
        """Parse command text into command and arguments.

        Args:
            text: Command text

        Returns:
            Tuple of (command, arguments)
        """
        parts = text.strip().split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        return cmd, args

    async def execute(self, text: str) -> CommandResult:
        """Execute a command.

        Args:
            text: Command text

        Returns:
            CommandResult indicating outcome
        """
        cmd, args = self.parse_command(text)

        if cmd not in self._commands:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type /help for available commands.")
            return CommandResult.ERROR

        command = self._commands[cmd]

        # Validate argument count
        if len(args) < command.min_args:
            self.console.print(f"[red]Missing arguments for {cmd}[/red]")
            self.console.print(f"Usage: {command.usage}")
            return CommandResult.ERROR

        if command.max_args is not None and len(args) > command.max_args:
            self.console.print(f"[red]Too many arguments for {cmd}[/red]")
            self.console.print(f"Usage: {command.usage}")
            return CommandResult.ERROR

        # Execute handler
        try:
            return await command.handler(args)
        except Exception as e:
            self.console.print(f"[red]Error executing {cmd}: {e}[/red]")
            return CommandResult.ERROR

    # Command handlers

    async def _cmd_help(self, args: list[str]) -> CommandResult:
        """Show help information."""
        if args:
            # Help for specific command
            cmd_name = args[0] if args[0].startswith("/") else f"/{args[0]}"
            if cmd_name in self._commands:
                cmd = self._commands[cmd_name]
                self.console.print(Panel(
                    f"[bold]{cmd.name}[/bold]\n\n"
                    f"{cmd.description}\n\n"
                    f"[dim]Usage:[/dim] {cmd.usage}\n"
                    f"[dim]Aliases:[/dim] {', '.join(cmd.aliases) or 'None'}\n"
                    f"[dim]Category:[/dim] {cmd.category}",
                    title="Command Help",
                    border_style="blue",
                ))
            else:
                self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
            return CommandResult.SUCCESS

        # General help - grouped by category
        self.console.print()
        self.console.print("[bold]CodeCrew Commands[/bold]")
        self.console.print()

        # Get unique commands grouped by category
        by_category: dict[str, list[Command]] = {}
        seen = set()
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                if cmd.category not in by_category:
                    by_category[cmd.category] = []
                by_category[cmd.category].append(cmd)

        # Display in a specific order
        category_order = ["Session", "Display", "Navigation", "Messages", "Git", "Information", "System"]
        category_colors = {
            "Session": "green",
            "Display": "yellow",
            "Navigation": "cyan",
            "Messages": "magenta",
            "Git": "bright_magenta",
            "Information": "blue",
            "System": "red",
        }

        for category in category_order:
            if category in by_category:
                color = category_colors.get(category, "white")
                self.console.print(f"  [{color}]{category}[/{color}]")
                for cmd in sorted(by_category[category], key=lambda c: c.name):
                    aliases_str = f" [dim]({', '.join(cmd.aliases)})[/dim]" if cmd.aliases else ""
                    self.console.print(f"    {cmd.name:12}{aliases_str:20} {cmd.description}")
                self.console.print()

        # Show any remaining categories
        for category in sorted(by_category.keys()):
            if category not in category_order:
                self.console.print(f"  [white]{category}[/white]")
                for cmd in sorted(by_category[category], key=lambda c: c.name):
                    self.console.print(f"    {cmd.name:12} {cmd.description}")
                self.console.print()

        self.console.print("[dim]Tips:[/dim]")
        self.console.print("[dim]  - Use @model to mention a specific AI (e.g., @claude, @gpt, @all)[/dim]")
        self.console.print("[dim]  - Type /help <command> for detailed help on a command[/dim]")
        self.console.print("[dim]  - Use /keys to see keyboard shortcuts[/dim]")
        return CommandResult.SUCCESS

    async def _cmd_quit(self, args: list[str]) -> CommandResult:
        """Exit the application."""
        return CommandResult.EXIT

    async def _cmd_clear(self, args: list[str]) -> CommandResult:
        """Clear the screen."""
        self.console.clear()
        return CommandResult.SUCCESS

    async def _cmd_new(self, args: list[str]) -> CommandResult:
        """Start a new session."""
        name = args[0] if args else None
        await self.app.new_session(name)
        self.console.print("[green]Started new session[/green]")
        return CommandResult.SUCCESS

    async def _cmd_sessions(self, args: list[str]) -> CommandResult:
        """List saved sessions."""
        limit = int(args[0]) if args else 20
        sessions = await self.app.list_sessions(limit)

        if not sessions:
            self.console.print("[dim]No saved sessions[/dim]")
            return CommandResult.SUCCESS

        table = Table(title="Saved Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Updated", style="yellow")

        for session in sessions:
            table.add_row(
                session.get("id", "")[:8] + "...",
                session.get("name", "-") or "-",
                session.get("updated_at", "-")[:16] if session.get("updated_at") else "-",
            )

        self.console.print(table)
        return CommandResult.SUCCESS

    async def _cmd_load(self, args: list[str]) -> CommandResult:
        """Load a session."""
        session_id = args[0]
        success = await self.app.load_session(session_id)
        if success:
            self.console.print(f"[green]Loaded session {session_id}[/green]")
        else:
            self.console.print(f"[red]Session not found: {session_id}[/red]")
            return CommandResult.ERROR
        return CommandResult.SUCCESS

    async def _cmd_save(self, args: list[str]) -> CommandResult:
        """Save current session."""
        name = args[0] if args else None
        await self.app.save_session(name)
        self.console.print("[green]Session saved[/green]")
        return CommandResult.SUCCESS

    async def _cmd_export(self, args: list[str]) -> CommandResult:
        """Export current session."""
        format_type = args[0] if args else "md"
        if format_type not in ("md", "json", "markdown"):
            self.console.print(f"[red]Unknown format: {format_type}[/red]")
            self.console.print("Available formats: md, json")
            return CommandResult.ERROR

        path = await self.app.export_session(format_type)
        self.console.print(f"[green]Exported to {path}[/green]")
        return CommandResult.SUCCESS

    async def _cmd_pin(self, args: list[str]) -> CommandResult:
        """Pin a message."""
        try:
            msg_num = int(args[0])
            await self.app.pin_message(msg_num)
            self.console.print(f"[green]Pinned message {msg_num}[/green]")
        except ValueError:
            self.console.print("[red]Invalid message number[/red]")
            return CommandResult.ERROR
        return CommandResult.SUCCESS

    async def _cmd_unpin(self, args: list[str]) -> CommandResult:
        """Unpin a message."""
        try:
            msg_num = int(args[0])
            await self.app.unpin_message(msg_num)
            self.console.print(f"[green]Unpinned message {msg_num}[/green]")
        except ValueError:
            self.console.print("[red]Invalid message number[/red]")
            return CommandResult.ERROR
        return CommandResult.SUCCESS

    async def _cmd_stats(self, args: list[str]) -> CommandResult:
        """Show conversation statistics."""
        stats = await self.app.get_stats()

        panel_content = Text()
        panel_content.append("Messages: ", style="dim")
        panel_content.append(f"{stats.get('message_count', 0)}\n")
        panel_content.append("Total Tokens: ", style="dim")
        panel_content.append(f"{stats.get('total_tokens', 0):,}\n")
        panel_content.append("Estimated Cost: ", style="dim")
        panel_content.append(f"${stats.get('total_cost', 0):.4f}\n")

        if stats.get("by_model"):
            panel_content.append("\nBy Model:\n", style="bold")
            for model, model_stats in stats["by_model"].items():
                panel_content.append(f"  {model}: ", style="cyan")
                panel_content.append(f"{model_stats.get('messages', 0)} messages, ")
                panel_content.append(f"{model_stats.get('tokens', 0):,} tokens\n")

        self.console.print(Panel(panel_content, title="Conversation Statistics", border_style="blue"))
        return CommandResult.SUCCESS

    async def _cmd_models(self, args: list[str]) -> CommandResult:
        """Show model status."""
        models = self.app.get_available_models()

        table = Table(title="Model Status")
        table.add_column("Model", style="bold")
        table.add_column("Status", justify="center")

        model_colors = {
            "claude": "orange3",
            "gpt": "green",
            "gemini": "blue",
            "grok": "purple",
        }

        for model in ["claude", "gpt", "gemini", "grok"]:
            color = model_colors.get(model, "white")
            available = model in models
            status = "[green]Available[/green]" if available else "[red]Unavailable[/red]"
            table.add_row(f"[{color}]{model.capitalize()}[/{color}]", status)

        self.console.print(table)
        return CommandResult.SUCCESS

    async def _cmd_config(self, args: list[str]) -> CommandResult:
        """Show current configuration."""
        config = self.app.get_config()

        panel_content = Text()
        panel_content.append("Theme: ", style="dim")
        panel_content.append(f"{config.get('theme', 'default')}\n")
        panel_content.append("Turn Strategy: ", style="dim")
        panel_content.append(f"{config.get('first_responder', 'rotate')}\n")
        panel_content.append("Silence Threshold: ", style="dim")
        panel_content.append(f"{config.get('silence_threshold', 0.3)}\n")
        panel_content.append("Auto-save: ", style="dim")
        panel_content.append(f"{config.get('auto_save', True)}\n")

        self.console.print(Panel(panel_content, title="Configuration", border_style="blue"))
        return CommandResult.SUCCESS

    async def _cmd_theme(self, args: list[str]) -> CommandResult:
        """Change color theme."""
        from codecrew.ui.theme import list_themes

        if not args:
            # List available themes
            themes = list_themes()
            self.console.print(f"Available themes: {', '.join(themes)}")
            self.console.print(f"Current theme: {self.app.current_theme}")
            return CommandResult.SUCCESS

        theme_name = args[0].lower()
        if self.app.set_theme(theme_name):
            self.console.print(f"[green]Theme changed to {theme_name}[/green]")
        else:
            self.console.print(f"[red]Unknown theme: {theme_name}[/red]")
            return CommandResult.ERROR
        return CommandResult.SUCCESS

    async def _cmd_compact(self, args: list[str]) -> CommandResult:
        """Toggle compact mode."""
        self.app.toggle_compact_mode()
        mode = "on" if self.app.compact_mode else "off"
        self.console.print(f"[green]Compact mode {mode}[/green]")
        return CommandResult.SUCCESS

    async def _cmd_decisions(self, args: list[str]) -> CommandResult:
        """Toggle showing model decisions."""
        self.app.toggle_show_decisions()
        mode = "on" if self.app.show_decisions else "off"
        self.console.print(f"[green]Show decisions {mode}[/green]")
        return CommandResult.SUCCESS

    async def _cmd_keys(self, args: list[str]) -> CommandResult:
        """Show keyboard shortcuts."""
        if hasattr(self.app, "keybinding_manager") and self.app.keybinding_manager:
            help_text = self.app.keybinding_manager.format_bindings_help()
            self.console.print(Panel(help_text, title="Keyboard Shortcuts", border_style="blue"))
        else:
            # Fallback to showing default keybindings
            from codecrew.ui.keybindings import DEFAULT_BINDINGS

            self.console.print()
            self.console.print("[bold]Keyboard Shortcuts[/bold]")
            self.console.print()

            # Group by category
            categories: dict[str, list[tuple[str, str, str]]] = {}
            for key, (action, desc, category) in DEFAULT_BINDINGS.items():
                if category not in categories:
                    categories[category] = []
                categories[category].append((key, action, desc))

            category_order = ["display", "navigation", "editing", "session"]
            for category in category_order:
                if category in categories:
                    self.console.print(f"  [cyan]{category.title()}[/cyan]")
                    for key, action, desc in sorted(categories[category]):
                        # Format key for display
                        display_key = key.replace("c-", "Ctrl+").replace("s-", "Shift+")
                        display_key = display_key.replace("pageup", "Page Up").replace("pagedown", "Page Down")
                        self.console.print(f"    {display_key:15} {desc}")
                    self.console.print()

        return CommandResult.SUCCESS

    async def _cmd_copy(self, args: list[str]) -> CommandResult:
        """Copy message to clipboard."""
        from codecrew.ui.clipboard import ClipboardManager

        if not ClipboardManager.is_available():
            self.console.print("[red]Clipboard not available on this system[/red]")
            return CommandResult.ERROR

        if args:
            # Copy specific message
            try:
                msg_num = int(args[0])
                content = await self.app.get_message_content(msg_num)
                if content:
                    if ClipboardManager.copy(content):
                        self.console.print(f"[green]Copied message {msg_num} to clipboard[/green]")
                    else:
                        self.console.print("[red]Failed to copy to clipboard[/red]")
                        return CommandResult.ERROR
                else:
                    self.console.print(f"[red]Message {msg_num} not found[/red]")
                    return CommandResult.ERROR
            except ValueError:
                self.console.print("[red]Invalid message number[/red]")
                return CommandResult.ERROR
        else:
            # Copy selected or last message
            if hasattr(self.app, "navigation_manager") and self.app.navigation_manager:
                msg = self.app.navigation_manager.get_selected_message()
                if msg:
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if ClipboardManager.copy(content):
                        self.console.print("[green]Copied selected message to clipboard[/green]")
                    else:
                        self.console.print("[red]Failed to copy to clipboard[/red]")
                        return CommandResult.ERROR
                else:
                    self.console.print("[yellow]No message selected. Use /copy <number> to copy a specific message.[/yellow]")
                    return CommandResult.ERROR
            else:
                # Fall back to last message
                content = await self.app.get_last_message_content()
                if content:
                    if ClipboardManager.copy(content):
                        self.console.print("[green]Copied last message to clipboard[/green]")
                    else:
                        self.console.print("[red]Failed to copy to clipboard[/red]")
                        return CommandResult.ERROR
                else:
                    self.console.print("[yellow]No messages to copy[/yellow]")
                    return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_search(self, args: list[str]) -> CommandResult:
        """Search messages."""
        query = " ".join(args)

        if hasattr(self.app, "navigation_manager") and self.app.navigation_manager:
            count = self.app.navigation_manager.search(query)
            if count > 0:
                self.console.print(f"[green]Found {count} matches for '{query}'[/green]")
                # Go to first match
                result = self.app.navigation_manager.current_match()
                if result:
                    self.console.print(f"[dim]Showing match 1 of {count} (use n/N to navigate)[/dim]")
            else:
                self.console.print(f"[yellow]No matches found for '{query}'[/yellow]")
        else:
            # Fallback: search through messages directly
            matches = await self.app.search_messages(query)
            if matches:
                self.console.print(f"[green]Found {len(matches)} messages matching '{query}':[/green]")
                for i, match in enumerate(matches[:10], 1):
                    preview = match.get("content", "")[:50] + "..." if len(match.get("content", "")) > 50 else match.get("content", "")
                    self.console.print(f"  {match.get('index', i)}: {preview}")
                if len(matches) > 10:
                    self.console.print(f"  [dim]... and {len(matches) - 10} more[/dim]")
            else:
                self.console.print(f"[yellow]No matches found for '{query}'[/yellow]")

        return CommandResult.SUCCESS

    async def _cmd_goto(self, args: list[str]) -> CommandResult:
        """Jump to a specific message."""
        identifier = args[0]

        if hasattr(self.app, "navigation_manager") and self.app.navigation_manager:
            if self.app.navigation_manager.goto_message(identifier):
                self.console.print(f"[green]Jumped to message {identifier}[/green]")
            else:
                self.console.print(f"[red]Message not found: {identifier}[/red]")
                return CommandResult.ERROR
        else:
            # Fallback
            try:
                msg_num = int(identifier)
                success = await self.app.scroll_to_message(msg_num)
                if success:
                    self.console.print(f"[green]Jumped to message {msg_num}[/green]")
                else:
                    self.console.print(f"[red]Message {msg_num} not found[/red]")
                    return CommandResult.ERROR
            except ValueError:
                self.console.print(f"[red]Invalid message identifier: {identifier}[/red]")
                return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_history(self, args: list[str]) -> CommandResult:
        """Show input history."""
        limit = int(args[0]) if args else 20

        if hasattr(self.app, "history_manager") and self.app.history_manager:
            entries = await self.app.history_manager.get_recent(limit=limit)

            if not entries:
                self.console.print("[dim]No input history[/dim]")
                return CommandResult.SUCCESS

            table = Table(title=f"Input History (last {len(entries)})")
            table.add_column("#", style="dim", width=4)
            table.add_column("Type", style="cyan", width=8)
            table.add_column("Content")
            table.add_column("Time", style="dim", width=16)

            for i, entry in enumerate(entries, 1):
                content = entry.content[:60] + "..." if len(entry.content) > 60 else entry.content
                content = content.replace("\n", " ")
                time_str = entry.timestamp.strftime("%H:%M:%S")
                table.add_row(str(i), entry.entry_type, content, time_str)

            self.console.print(table)
        else:
            self.console.print("[yellow]History manager not available[/yellow]")

        return CommandResult.SUCCESS

    # Git command handlers

    async def _cmd_git(self, args: list[str]) -> CommandResult:
        """Show Git operations overview."""
        try:
            from codecrew.git import GitRepository, GitError

            repo = GitRepository.find()
            if not repo:
                self.console.print("[yellow]Not in a git repository[/yellow]")
                return CommandResult.SUCCESS

            status = repo.get_status()

            self.console.print()
            self.console.print(f"[bold]Git Repository[/bold] - [cyan]{repo.root}[/cyan]")
            self.console.print()
            self.console.print(f"  Branch: [green]{status.branch}[/green]")

            if status.upstream:
                tracking = []
                if status.ahead > 0:
                    tracking.append(f"[yellow]↑{status.ahead}[/yellow]")
                if status.behind > 0:
                    tracking.append(f"[yellow]↓{status.behind}[/yellow]")
                tracking_str = " ".join(tracking) if tracking else "[green]up to date[/green]"
                self.console.print(f"  Tracking: {status.upstream} ({tracking_str})")

            self.console.print()

            # Summary counts
            changes = []
            if status.staged:
                changes.append(f"[green]{len(status.staged)} staged[/green]")
            if status.modified:
                changes.append(f"[yellow]{len(status.modified)} modified[/yellow]")
            if status.deleted:
                changes.append(f"[red]{len(status.deleted)} deleted[/red]")
            if status.untracked:
                changes.append(f"[dim]{len(status.untracked)} untracked[/dim]")
            if status.conflicted:
                changes.append(f"[red bold]{len(status.conflicted)} conflicts[/red bold]")

            if changes:
                self.console.print(f"  Changes: {', '.join(changes)}")
            else:
                self.console.print("  [dim]Working tree clean[/dim]")

            self.console.print()
            self.console.print("[dim]Commands: /status, /diff, /log, /branch[/dim]")

        except ImportError:
            self.console.print("[red]Git module not available[/red]")
            return CommandResult.ERROR
        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
            return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_status(self, args: list[str]) -> CommandResult:
        """Show detailed git status."""
        try:
            from codecrew.git import GitRepository, GitError

            repo = GitRepository.find()
            if not repo:
                self.console.print("[yellow]Not in a git repository[/yellow]")
                return CommandResult.SUCCESS

            status = repo.get_status()

            self.console.print()
            self.console.print(f"On branch [green]{status.branch}[/green]")

            if status.upstream:
                tracking = []
                if status.ahead > 0:
                    tracking.append(f"ahead {status.ahead}")
                if status.behind > 0:
                    tracking.append(f"behind {status.behind}")
                if tracking:
                    self.console.print(f"Your branch is {' and '.join(tracking)} of '{status.upstream}'")
                else:
                    self.console.print(f"Your branch is up to date with '{status.upstream}'")

            self.console.print()

            if status.staged:
                self.console.print("[green]Changes to be committed:[/green]")
                for change_type, filename in status.staged:
                    self.console.print(f"  [green]{change_type}:[/green] {filename}")
                self.console.print()

            if status.modified or status.deleted:
                self.console.print("[yellow]Changes not staged for commit:[/yellow]")
                for filename in status.modified:
                    self.console.print(f"  [yellow]modified:[/yellow] {filename}")
                for filename in status.deleted:
                    self.console.print(f"  [red]deleted:[/red] {filename}")
                self.console.print()

            if status.untracked:
                self.console.print("[dim]Untracked files:[/dim]")
                for filename in status.untracked:
                    self.console.print(f"  [dim]{filename}[/dim]")
                self.console.print()

            if status.conflicted:
                self.console.print("[red bold]Unmerged paths (conflicts):[/red bold]")
                for filename in status.conflicted:
                    self.console.print(f"  [red]both modified:[/red] {filename}")
                self.console.print()

            if status.is_clean:
                self.console.print("[dim]Nothing to commit, working tree clean[/dim]")

        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
            return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_diff(self, args: list[str]) -> CommandResult:
        """Show git diff."""
        try:
            from codecrew.git import GitRepository, GitError

            repo = GitRepository.find()
            if not repo:
                self.console.print("[yellow]Not in a git repository[/yellow]")
                return CommandResult.SUCCESS

            staged = False
            file_path = None

            # Parse arguments
            for arg in args:
                if arg == "--staged" or arg == "-s":
                    staged = True
                else:
                    file_path = arg

            diff = repo.get_diff(staged=staged, file=file_path)

            if not diff.content:
                if staged:
                    self.console.print("[dim]No staged changes[/dim]")
                else:
                    self.console.print("[dim]No unstaged changes[/dim]")
                return CommandResult.SUCCESS

            # Show summary
            self.console.print(f"[bold]{diff.summary()}[/bold]")
            self.console.print()

            # Syntax highlight diff output
            from rich.syntax import Syntax
            syntax = Syntax(diff.content, "diff", theme="monokai", line_numbers=False)
            self.console.print(syntax)

        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
            return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_log(self, args: list[str]) -> CommandResult:
        """Show recent commits."""
        try:
            from codecrew.git import GitRepository, GitError

            repo = GitRepository.find()
            if not repo:
                self.console.print("[yellow]Not in a git repository[/yellow]")
                return CommandResult.SUCCESS

            limit = int(args[0]) if args else 10
            commits = repo.get_log(limit=limit)

            if not commits:
                self.console.print("[dim]No commits found[/dim]")
                return CommandResult.SUCCESS

            self.console.print()
            for commit in commits:
                # Colored hash
                self.console.print(f"[yellow]{commit.short_hash}[/yellow] {commit.message}")
                self.console.print(f"  [dim]{commit.author} - {commit.date}[/dim]")
                self.console.print()

        except ValueError:
            self.console.print("[red]Invalid limit value[/red]")
            return CommandResult.ERROR
        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
            return CommandResult.ERROR

        return CommandResult.SUCCESS

    async def _cmd_branch(self, args: list[str]) -> CommandResult:
        """Show or manage branches."""
        try:
            from codecrew.git import GitRepository, GitError

            repo = GitRepository.find()
            if not repo:
                self.console.print("[yellow]Not in a git repository[/yellow]")
                return CommandResult.SUCCESS

            if args:
                # Create or switch to branch
                branch_name = args[0]
                branches = repo.get_branches()
                existing = [b.name for b in branches]

                if branch_name in existing:
                    # Switch to existing branch
                    result = repo.checkout(branch_name)
                    self.console.print(f"[green]Switched to branch '{branch_name}'[/green]")
                else:
                    # Create and switch to new branch
                    result = repo.checkout(branch_name, create=True)
                    self.console.print(f"[green]Created and switched to new branch '{branch_name}'[/green]")
            else:
                # List branches
                branches = repo.get_branches()

                if not branches:
                    self.console.print("[dim]No branches found[/dim]")
                    return CommandResult.SUCCESS

                self.console.print()
                for branch in branches:
                    if branch.is_current:
                        self.console.print(f"[green]* {branch.name}[/green]")
                    else:
                        self.console.print(f"  {branch.name}")
                self.console.print()

        except Exception as e:
            self.console.print(f"[red]Git error: {e}[/red]")
            return CommandResult.ERROR

        return CommandResult.SUCCESS

    def get_commands_for_completion(self) -> list[str]:
        """Get list of command names for autocomplete.

        Returns:
            List of all command names including aliases
        """
        return list(self._commands.keys())

    def get_command_categories(self) -> dict[str, list[Command]]:
        """Get commands grouped by category.

        Returns:
            Dict of category name to list of commands
        """
        by_category: dict[str, list[Command]] = {}
        seen = set()
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                if cmd.category not in by_category:
                    by_category[cmd.category] = []
                by_category[cmd.category].append(cmd)
        return by_category
