"""CLI entry point for CodeCrew."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codecrew import __version__
from codecrew.config import create_default_config, get_settings, load_settings
from codecrew.conversation import DatabaseManager

app = typer.Typer(
    name="codecrew",
    help="AI Coding Groupchat CLI - Multiple AI models collaborating in a group chat",
    add_completion=True,
    no_args_is_help=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold]CodeCrew[/bold] version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    resume: Optional[str] = typer.Option(
        None,
        "--resume",
        "-r",
        help="Resume a previous session (use 'last' for most recent)",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """CodeCrew - AI Coding Groupchat CLI.

    Start an interactive session with multiple AI models collaborating
    in a group chat environment.
    """
    # If a subcommand is being invoked, don't enter interactive mode
    if ctx.invoked_subcommand is not None:
        return

    # Load configuration
    if config:
        load_settings(config_path=config, force_reload=True)

    # Create default config if it doesn't exist
    create_default_config()

    # Enter interactive mode
    asyncio.run(start_interactive(resume=resume, verbose=verbose))


async def start_interactive(
    resume: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Start the interactive chat session."""
    settings = get_settings()

    # Initialize database
    db = DatabaseManager(settings.storage.resolved_database_path)
    await db.initialize()

    # Check for available models
    available_models = settings.get_available_models()
    if not available_models:
        console.print(
            Panel(
                "[yellow]No API keys configured![/yellow]\n\n"
                "Please set at least one API key:\n"
                "  • ANTHROPIC_API_KEY for Claude\n"
                "  • OPENAI_API_KEY for GPT\n"
                "  • GOOGLE_API_KEY for Gemini\n"
                "  • XAI_API_KEY for Grok\n\n"
                "Or configure them in ~/.codecrew/config.yaml",
                title="Configuration Required",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)

    # Import and create the TUI app
    from codecrew.conversation import ConversationManager
    from codecrew.models import create_model_clients
    from codecrew.orchestrator import create_persistent_orchestrator
    from codecrew.tools import (
        PermissionManager,
        ToolExecutor,
        ToolRegistry,
        register_builtin_tools,
    )
    from codecrew.ui import ChatApp

    try:
        # Create model clients
        clients = create_model_clients(settings)

        # Create tool system
        registry = ToolRegistry()
        register_builtin_tools(registry)
        permissions = PermissionManager(auto_approve=False)
        executor = ToolExecutor(registry=registry, permissions=permissions)

        # Create orchestrator with persistence and tools
        from codecrew.orchestrator.tool_orchestrator import ToolEnabledOrchestrator

        # First create base persistent orchestrator
        base_orchestrator = await create_persistent_orchestrator(
            clients=clients,
            settings=settings,
            db_path=settings.storage.resolved_database_path,
            enable_summarization=True,
        )

        # Wrap with tool capabilities
        orchestrator = ToolEnabledOrchestrator(
            clients=clients,
            settings=settings,
            tool_executor=executor,
            tool_registry=registry,
        )

        # Create conversation manager for the app
        conversation_manager = ConversationManager(
            db=db,
            orchestrator=base_orchestrator,
        )

        # Create and run the TUI app
        app = ChatApp(
            settings=settings,
            orchestrator=orchestrator,
            conversation_manager=conversation_manager,
            resume_session=resume,
            theme_name=settings.ui.theme,  # type: ignore
        )

        await app.run()

    except ImportError as e:
        # Fallback if TUI components have import issues
        console.print(f"[red]Error loading TUI: {e}[/red]")
        console.print("[dim]Run 'codecrew --help' to see available commands.[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def sessions(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of sessions to show"),
) -> None:
    """List saved conversation sessions."""
    asyncio.run(_list_sessions(limit))


async def _list_sessions(limit: int) -> None:
    """List sessions from database."""
    settings = get_settings()
    db = DatabaseManager(settings.storage.resolved_database_path)

    try:
        await db.initialize()
        session_list = await db.list_sessions(limit=limit)

        if not session_list:
            console.print("[dim]No sessions found.[/dim]")
            return

        table = Table(title="Saved Sessions")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Project", style="blue")
        table.add_column("Updated", style="yellow")

        for session in session_list:
            table.add_row(
                session["id"][:8] + "...",
                session["name"] or "-",
                session["project_path"] or "-",
                session["updated_at"][:16] if session["updated_at"] else "-",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing sessions: {e}[/red]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
) -> None:
    """Search through conversation history."""
    asyncio.run(_search_sessions(query))


async def _search_sessions(query: str) -> None:
    """Search sessions by query."""
    settings = get_settings()
    db = DatabaseManager(settings.storage.resolved_database_path)

    try:
        await db.initialize()
        results = await db.search_sessions(query)

        if not results:
            console.print(f"[dim]No sessions found matching '{query}'[/dim]")
            return

        table = Table(title=f"Search Results for '{query}'")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Project", style="blue")
        table.add_column("Updated", style="yellow")

        for session in results:
            table.add_row(
                session["id"][:8] + "...",
                session["name"] or "-",
                session["project_path"] or "-",
                session["updated_at"][:16] if session["updated_at"] else "-",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error searching sessions: {e}[/red]")


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    format: str = typer.Option("md", "--format", "-f", help="Export format (md or json)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export a conversation session."""
    asyncio.run(_export_session(session_id, format, output))


async def _export_session(session_id: str, format: str, output: Optional[Path]) -> None:
    """Export a session to file."""
    import json

    settings = get_settings()
    db = DatabaseManager(settings.storage.resolved_database_path)

    try:
        await db.initialize()

        # Find session (support partial ID matching)
        sessions = await db.list_sessions(limit=1000)
        matching = [s for s in sessions if s["id"].startswith(session_id)]

        if not matching:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise typer.Exit(1)

        if len(matching) > 1:
            console.print(f"[yellow]Multiple sessions match '{session_id}'. Please be more specific.[/yellow]")
            for s in matching[:5]:
                console.print(f"  {s['id']}")
            raise typer.Exit(1)

        session = matching[0]
        messages = await db.get_session_messages(session["id"])

        if format == "json":
            export_data = {
                "session": session,
                "messages": messages,
            }
            content = json.dumps(export_data, indent=2, default=str)
            ext = ".json"
        else:  # markdown
            lines = [
                f"# CodeCrew Session: {session['name'] or session['id'][:8]}",
                "",
                f"**Created:** {session['created_at']}",
                f"**Project:** {session['project_path'] or 'N/A'}",
                "",
                "---",
                "",
            ]

            for msg in messages:
                role = msg["role"].upper()
                model = f" ({msg['model']})" if msg["model"] else ""
                lines.append(f"### {role}{model}")
                lines.append("")
                lines.append(msg["content"])
                lines.append("")

            content = "\n".join(lines)
            ext = ".md"

        if output:
            output.write_text(content, encoding="utf-8")
            console.print(f"[green]Exported to {output}[/green]")
        else:
            # Generate default filename
            filename = f"codecrew_session_{session['id'][:8]}{ext}"
            Path(filename).write_text(content, encoding="utf-8")
            console.print(f"[green]Exported to {filename}[/green]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error exporting session: {e}[/red]")


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    console.print(Panel("[bold]Current Configuration[/bold]", border_style="blue"))

    # API Keys (masked)
    console.print("\n[bold]API Keys:[/bold]")
    console.print(f"  Anthropic: {'✓ Set' if settings.anthropic_api_key else '✗ Not set'}")
    console.print(f"  OpenAI:    {'✓ Set' if settings.openai_api_key else '✗ Not set'}")
    console.print(f"  Google:    {'✓ Set' if settings.google_api_key else '✗ Not set'}")
    console.print(f"  xAI:       {'✓ Set' if settings.xai_api_key else '✗ Not set'}")

    # Models
    console.print("\n[bold]Models:[/bold]")
    for name in ["claude", "gpt", "gemini", "grok"]:
        model_config = getattr(settings.models, name)
        status = "enabled" if model_config.enabled else "disabled"
        console.print(f"  {name}: {model_config.model_id} [{status}]")

    # Available models
    available = settings.get_available_models()
    console.print(f"\n[bold]Available models:[/bold] {', '.join(available) if available else 'None'}")

    # Conversation settings
    console.print("\n[bold]Conversation:[/bold]")
    console.print(f"  First responder: {settings.conversation.first_responder}")
    console.print(f"  Silence threshold: {settings.conversation.silence_threshold}")
    console.print(f"  Auto-save: {settings.conversation.auto_save}")

    # Storage
    console.print("\n[bold]Storage:[/bold]")
    console.print(f"  Database: {settings.storage.resolved_database_path}")


@app.command()
def models() -> None:
    """Show model status and availability."""
    settings = get_settings()

    table = Table(title="Model Status")
    table.add_column("Model", style="bold")
    table.add_column("Model ID")
    table.add_column("Enabled", justify="center")
    table.add_column("API Key", justify="center")
    table.add_column("Available", justify="center")

    model_names = ["claude", "gpt", "gemini", "grok"]
    colors = {
        "claude": "orange3",
        "gpt": "green",
        "gemini": "blue",
        "grok": "purple",
    }

    for name in model_names:
        model_config = getattr(settings.models, name)
        has_key = settings.has_api_key(name)
        available = model_config.enabled and has_key

        table.add_row(
            f"[{colors[name]}]{name.capitalize()}[/{colors[name]}]",
            model_config.model_id,
            "✓" if model_config.enabled else "✗",
            "✓" if has_key else "✗",
            "[green]✓[/green]" if available else "[red]✗[/red]",
        )

    console.print(table)


if __name__ == "__main__":
    app()
