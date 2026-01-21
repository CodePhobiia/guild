"""Main TUI application for CodeCrew."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from codecrew import __version__
from codecrew.config import Settings
from codecrew.models.types import ToolCall
from codecrew.orchestrator.events import EventType, OrchestratorEvent
from codecrew.ui.components.header import Header
from codecrew.ui.components.input_area import InputArea, render_input_hint
from codecrew.ui.components.message_list import MessageList
from codecrew.ui.components.status_bar import StatusBar
from codecrew.ui.components.tool_panel import ToolPanel
from codecrew.ui.dialogs.permission import PermissionDialog, PermissionResponse
from codecrew.ui.dialogs.session_picker import ConfirmationDialog, SessionPicker
from codecrew.ui.handlers.commands import CommandHandler, CommandResult
from codecrew.ui.handlers.events import EventHandler
from codecrew.ui.theme import Theme, ThemeName, get_theme

logger = logging.getLogger(__name__)


class ChatApp:
    """Main TUI application for CodeCrew.

    Manages the interactive chat interface including:
    - Message display with streaming
    - Input handling with @mention completion
    - Tool execution visualization
    - Session management
    - Command processing
    """

    def __init__(
        self,
        settings: Settings,
        orchestrator: Any,  # ToolEnabledOrchestrator or PersistentOrchestrator
        conversation_manager: Optional[Any] = None,
        resume_session: Optional[str] = None,
        theme_name: ThemeName = "default",
    ):
        """Initialize the chat application.

        Args:
            settings: Application settings
            orchestrator: Orchestrator instance for message processing
            conversation_manager: Optional conversation manager for persistence
            resume_session: Optional session ID to resume
            theme_name: Theme to use
        """
        self.settings = settings
        self.orchestrator = orchestrator
        self.conversation_manager = conversation_manager
        self.resume_session = resume_session

        # Initialize theme
        self.current_theme = theme_name
        self.theme = get_theme(theme_name)

        # Get available models
        self.available_models = settings.get_available_models()

        # Console for output
        self.console = Console()

        # UI state
        self.running = False
        self.compact_mode = False
        self.show_decisions = settings.ui.show_silent_models
        self._current_session_id: Optional[str] = None
        self._current_session_name: Optional[str] = None
        self._live_context: Optional[Live] = None  # For streaming display

        # Initialize components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize UI components."""
        use_unicode = True  # Could make configurable

        # Header
        self.header = Header(
            theme=self.theme,
            available_models=self.available_models,
            version=__version__,
        )

        # Message list
        self.message_list = MessageList(
            theme=self.theme,
            code_theme=self.settings.ui.code_theme,
            use_unicode=use_unicode,
            show_decisions=self.show_decisions,
        )

        # Status bar
        self.status_bar = StatusBar(
            theme=self.theme,
            use_unicode=use_unicode,
            max_tokens=self.settings.conversation.max_context_tokens,
            show_cost=self.settings.ui.show_cost_estimate,
        )

        # Tool panel
        self.tool_panel = ToolPanel(
            theme=self.theme,
            use_unicode=use_unicode,
        )

        # Input area
        self.input_area = InputArea(
            theme=self.theme,
            models=self.available_models,
            multiline=True,
        )

        # Event handler
        self.event_handler = EventHandler(
            message_list=self.message_list,
            status_bar=self.status_bar,
            tool_panel=self.tool_panel,
            on_permission_request=self._handle_permission_request,
            on_error=self._handle_error,
        )

        # Command handler
        self.command_handler = CommandHandler(self)

        # Dialogs
        self.permission_dialog = PermissionDialog(
            theme=self.theme,
            console=self.console,
        )
        self.session_picker = SessionPicker(
            console=self.console,
            theme=self.theme,
        )
        self.confirm_dialog = ConfirmationDialog(
            console=self.console,
            theme=self.theme,
        )

    async def run(self) -> None:
        """Run the chat application main loop."""
        self.running = True

        # Resume or create session
        if self.resume_session:
            await self._resume_session(self.resume_session)
        else:
            await self._show_welcome()

        # Main loop
        while self.running:
            try:
                # Get user input
                user_input = await self._get_input()

                if user_input is None:
                    continue

                # Process input
                await self._process_input(user_input)

            except EOFError:
                # Ctrl+D - exit
                self.running = False
            except KeyboardInterrupt:
                # Ctrl+C - cancel current operation
                self.message_list.clear_indicators()
                self.status_bar.set_status("idle")
                self.console.print("\n[dim]Cancelled[/dim]")

        # Cleanup
        await self._cleanup()

    async def _show_welcome(self) -> None:
        """Show welcome message."""
        self.console.print()
        self.console.print(Panel(
            f"[bold]Welcome to CodeCrew![/bold]\n\n"
            f"Available models: {', '.join(self.available_models)}\n"
            f"Type your message to start chatting.\n"
            f"Use @claude, @gpt, @gemini, @grok to mention specific models.\n"
            f"Type /help for commands, /quit to exit.",
            title=f"CodeCrew v{__version__}",
            border_style="blue",
        ))
        self.console.print()

    async def _resume_session(self, session_id: str) -> None:
        """Resume an existing session.

        Args:
            session_id: Session ID or "last" for most recent
        """
        if not self.conversation_manager:
            self.console.print("[yellow]Session management not available[/yellow]")
            await self._show_welcome()
            return

        try:
            if session_id == "last":
                sessions = await self.conversation_manager.list_sessions(limit=1)
                if sessions:
                    session_id = sessions[0].get("id")
                else:
                    self.console.print("[yellow]No previous sessions found[/yellow]")
                    await self._show_welcome()
                    return

            # Load the session
            session = await self.conversation_manager.load_session(session_id)
            if session:
                self._current_session_id = session.get("id")
                self._current_session_name = session.get("name")
                self.header.set_session(
                    name=self._current_session_name,
                    session_id=self._current_session_id,
                )
                self.console.print(
                    f"[green]Resumed session: "
                    f"{self._current_session_name or self._current_session_id[:8]}[/green]"
                )
                self.console.print()
            else:
                self.console.print(f"[red]Session not found: {session_id}[/red]")
                await self._show_welcome()

        except Exception as e:
            self.console.print(f"[red]Error resuming session: {e}[/red]")
            await self._show_welcome()

    async def _get_input(self) -> Optional[str]:
        """Get user input.

        Returns:
            User input string or None
        """
        try:
            # Show input hint
            self.console.print(render_input_hint(self.theme), end="")
            self.console.print()

            # Get input
            user_input = await self.input_area.prompt_async()
            return user_input.strip() if user_input else None

        except EOFError:
            raise
        except KeyboardInterrupt:
            return None

    async def _process_input(self, user_input: str) -> None:
        """Process user input.

        Args:
            user_input: The user's input
        """
        if not user_input:
            return

        # Check if it's a command
        if self.command_handler.is_command(user_input):
            result = await self.command_handler.execute(user_input)
            if result == CommandResult.EXIT:
                self.running = False
            return

        # Add user message to display
        self.message_list.add_user_message(user_input)
        self.console.print(self.message_list._render_item(
            self.message_list._items[-1]
        ))

        # Process through orchestrator
        await self._process_message(user_input)

    async def _process_message(self, message: str) -> None:
        """Process a message through the orchestrator.

        Args:
            message: User message
        """
        self.status_bar.set_status("thinking")
        self._live_context: Optional[Live] = None

        try:
            # Start thinking indicator
            self.message_list.start_thinking(self.available_models)

            # Process message and handle events
            async for event in self.orchestrator.process_message(message, stream=True):
                await self._handle_event(event)

        except Exception as e:
            self.message_list.clear_indicators()
            self.message_list.add_error(str(e))
            self.status_bar.set_status("error", message=str(e))
            self.console.print(f"[red]Error: {e}[/red]")
        finally:
            # Clean up live context if still active
            if self._live_context is not None:
                self._live_context.stop()
                self._live_context = None

    async def _handle_event(self, event: OrchestratorEvent) -> None:
        """Handle an orchestrator event.

        Args:
            event: The event to handle
        """
        # Use event handler for most events
        await self.event_handler.handle(event)

        # Update display for key events
        if event.type == EventType.RESPONSE_CHUNK:
            # Update streaming display using Live for proper multi-line refresh
            if self.message_list._streaming:
                if self._live_context is None:
                    # Start a new Live context for streaming
                    self._live_context = Live(
                        self.message_list._streaming.render(),
                        console=self.console,
                        refresh_per_second=10,
                        transient=True,  # Will be replaced when complete
                    )
                    self._live_context.start()
                else:
                    # Update the existing Live context
                    self._live_context.update(self.message_list._streaming.render())
        elif event.type == EventType.RESPONSE_COMPLETE:
            # Stop Live context and show final message
            if self._live_context is not None:
                self._live_context.stop()
                self._live_context = None
            # Show complete message
            if self.message_list._items:
                self.console.print(self.message_list._render_item(
                    self.message_list._items[-1]
                ))
        elif event.type == EventType.TOOL_CALL:
            # Stop any active streaming before showing tool call
            if self._live_context is not None:
                self._live_context.stop()
                self._live_context = None
            # Show tool call
            if self.message_list._items:
                self.console.print(self.message_list._render_item(
                    self.message_list._items[-1]
                ))
        elif event.type == EventType.TOOL_RESULT:
            # Show tool result
            if self.message_list._items:
                self.console.print(self.message_list._render_item(
                    self.message_list._items[-1]
                ))
        elif event.type == EventType.ERROR:
            # Stop any active streaming before showing error
            if self._live_context is not None:
                self._live_context.stop()
                self._live_context = None
            self.console.print(f"[red]Error: {event.error}[/red]")
        elif event.type == EventType.TURN_COMPLETE:
            # Show turn summary
            if event.usage:
                self.console.print(
                    f"[dim]Turn complete: {event.usage.total_tokens} tokens[/dim]"
                )

    async def _handle_permission_request(
        self,
        model: str,
        tool_call: ToolCall,
        permission_request: Any,
    ) -> None:
        """Handle a tool permission request.

        Args:
            model: Model requesting permission
            tool_call: The tool call
            permission_request: Permission request details
        """
        # Get permission level from request
        level = getattr(permission_request, "level", "cautious")
        if hasattr(level, "value"):
            level = level.value

        # Show permission dialog
        response = await self.permission_dialog.show(
            model=model,
            tool_call=tool_call,
            permission_level=level,
        )

        # Handle response
        if response == PermissionResponse.ALLOW:
            # One-time allow - grant session permission so the current call proceeds
            # The session grant will be used for subsequent calls to the same tool
            if hasattr(self.orchestrator, "tool_executor"):
                self.orchestrator.tool_executor.permissions.grant_session_permission(
                    tool_call.name
                )
        elif response == PermissionResponse.ALWAYS:
            # Grant permanent permission for this tool by setting it to SAFE level
            if hasattr(self.orchestrator, "tool_executor"):
                from codecrew.tools.permissions import PermissionLevel
                self.orchestrator.tool_executor.permissions.set_tool_permission(
                    tool_call.name,
                    PermissionLevel.SAFE,
                )
        elif response == PermissionResponse.ALLOW_SESSION:
            # Grant session permission
            if hasattr(self.orchestrator, "tool_executor"):
                self.orchestrator.tool_executor.permissions.grant_session_permission(
                    tool_call.name
                )
        elif response == PermissionResponse.NEVER:
            # Block this tool
            if hasattr(self.orchestrator, "tool_executor"):
                self.orchestrator.tool_executor.permissions.block_tool(tool_call.name)
        # DENY is handled by default (permission not granted)

    def _handle_error(self, error: str) -> None:
        """Handle an error.

        Args:
            error: Error message
        """
        self.console.print(f"[red]Error: {error}[/red]")

    async def _cleanup(self) -> None:
        """Cleanup before exit."""
        # Save session if auto-save enabled
        if self.settings.conversation.auto_save and self.conversation_manager:
            try:
                await self.conversation_manager.save()
                self.console.print("[dim]Session saved[/dim]")
            except Exception as e:
                self.console.print(f"[yellow]Could not save session: {e}[/yellow]")

        self.console.print("[dim]Goodbye![/dim]")

    # Public methods for command handler

    async def new_session(self, name: Optional[str] = None) -> None:
        """Start a new session.

        Args:
            name: Optional session name
        """
        self.message_list.clear()
        self.tool_panel.clear()
        self.status_bar.reset()

        if self.conversation_manager:
            session = await self.conversation_manager.create_session(name=name)
            self._current_session_id = session.get("id")
            self._current_session_name = name

        self.header.set_session(name=name, session_id=self._current_session_id)

    async def list_sessions(self, limit: int = 20) -> list[dict]:
        """List saved sessions.

        Args:
            limit: Maximum sessions to return

        Returns:
            List of session dictionaries
        """
        if not self.conversation_manager:
            return []
        return await self.conversation_manager.list_sessions(limit=limit)

    async def load_session(self, session_id: str) -> bool:
        """Load a session.

        Args:
            session_id: Session ID (partial match supported)

        Returns:
            True if loaded successfully
        """
        if not self.conversation_manager:
            return False

        try:
            session = await self.conversation_manager.load_session(session_id)
            if session:
                self._current_session_id = session.get("id")
                self._current_session_name = session.get("name")
                self.header.set_session(
                    name=self._current_session_name,
                    session_id=self._current_session_id,
                )
                return True
            return False
        except (OSError, ValueError, KeyError) as e:
            logger.debug(f"Failed to load session: {e}")
            return False

    async def save_session(self, name: Optional[str] = None) -> None:
        """Save current session.

        Args:
            name: Optional new name for session
        """
        if self.conversation_manager:
            if name:
                await self.conversation_manager.rename_session(name)
                self._current_session_name = name
                self.header.set_session(name=name, session_id=self._current_session_id)
            await self.conversation_manager.save()
            self.status_bar.mark_saved()

    async def export_session(self, format_type: str = "md") -> str:
        """Export current session.

        Args:
            format_type: Export format (md or json)

        Returns:
            Path to exported file
        """
        if not self.conversation_manager:
            raise ValueError("Session management not available")

        content = await self.conversation_manager.export_session(format=format_type)
        ext = ".json" if format_type == "json" else ".md"
        filename = f"codecrew_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        Path(filename).write_text(content, encoding="utf-8")
        return filename

    async def pin_message(self, msg_num: int) -> None:
        """Pin a message.

        Args:
            msg_num: Message number (1-indexed)
        """
        if self.conversation_manager and 1 <= msg_num <= len(self.message_list._items):
            # Get message ID and pin it
            # Implementation depends on how messages are tracked
            pass

    async def unpin_message(self, msg_num: int) -> None:
        """Unpin a message.

        Args:
            msg_num: Message number (1-indexed)
        """
        if self.conversation_manager and 1 <= msg_num <= len(self.message_list._items):
            # Get message ID and unpin it
            # Implementation depends on how messages are tracked
            pass

    async def get_stats(self) -> dict[str, Any]:
        """Get conversation statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "message_count": self.message_list.message_count,
            "total_tokens": self.status_bar.total_tokens,
            "total_cost": self.status_bar.total_cost,
        }

        if self.conversation_manager:
            try:
                db_stats = await self.conversation_manager.get_conversation_stats()
                stats.update(db_stats)
            except (OSError, ValueError) as e:
                logger.debug(f"Failed to get conversation stats: {e}")

        return stats

    def get_available_models(self) -> list[str]:
        """Get list of available models.

        Returns:
            List of model names
        """
        return self.available_models

    def get_config(self) -> dict[str, Any]:
        """Get current configuration.

        Returns:
            Configuration dictionary
        """
        return {
            "theme": self.current_theme,
            "first_responder": self.settings.conversation.first_responder,
            "silence_threshold": self.settings.conversation.silence_threshold,
            "auto_save": self.settings.conversation.auto_save,
            "show_cost": self.settings.ui.show_cost_estimate,
            "show_token_usage": self.settings.ui.show_token_usage,
        }

    def set_theme(self, theme_name: str) -> bool:
        """Set the color theme.

        Args:
            theme_name: Theme name

        Returns:
            True if theme was set
        """
        try:
            self.theme = get_theme(theme_name)  # type: ignore
            self.current_theme = theme_name  # type: ignore
            self._init_components()  # Reinitialize with new theme
            return True
        except KeyError:
            return False

    def toggle_compact_mode(self) -> None:
        """Toggle compact display mode."""
        self.compact_mode = not self.compact_mode

    def toggle_show_decisions(self) -> None:
        """Toggle showing model decisions."""
        self.show_decisions = not self.show_decisions
        self.message_list.show_decisions = self.show_decisions


async def create_chat_app(
    settings: Settings,
    resume_session: Optional[str] = None,
) -> ChatApp:
    """Create and configure a ChatApp instance.

    Args:
        settings: Application settings
        resume_session: Optional session ID to resume

    Returns:
        Configured ChatApp instance
    """
    from codecrew.conversation import ConversationManager, DatabaseManager
    from codecrew.models import create_model_clients
    from codecrew.models.types import ToolCall as ToolCallType
    from codecrew.orchestrator import create_tool_enabled_orchestrator
    from codecrew.tools import (
        PermissionManager,
        ToolExecutor,
        ToolRegistry,
        register_builtin_tools,
    )
    from codecrew.tools.permissions import PermissionRequest

    # Initialize database
    db = DatabaseManager(settings.storage.resolved_database_path)
    await db.initialize()

    # Create model clients
    clients = create_model_clients(settings)

    # Create tool system
    registry = ToolRegistry()
    register_builtin_tools(registry)
    permissions = PermissionManager(auto_approve=False)
    executor = ToolExecutor(registry=registry, permissions=permissions)

    # Create orchestrator
    orchestrator = await create_tool_enabled_orchestrator(
        clients=clients,
        settings=settings,
        tool_executor=executor,
        tool_registry=registry,
    )

    # Create conversation manager
    conversation_manager = ConversationManager(
        db=db,
        orchestrator=orchestrator,
    )

    # Create app
    app = ChatApp(
        settings=settings,
        orchestrator=orchestrator,
        conversation_manager=conversation_manager,
        resume_session=resume_session,
        theme_name=settings.ui.theme,  # type: ignore
    )

    # Wire up the confirmation callback for tool permissions
    # This bridges the synchronous PermissionManager.check_permission() to the TUI dialog
    def confirmation_callback(request: PermissionRequest) -> bool:
        """Synchronous callback to request user confirmation for tool execution.

        Args:
            request: Permission request with tool details

        Returns:
            True if user grants permission, False otherwise
        """
        # Create a ToolCall object for the dialog
        tool_call = ToolCallType(
            id=f"perm_{request.tool_name}",
            name=request.tool_name,
            arguments=request.arguments,
        )

        # Show the permission dialog synchronously
        response = app.permission_dialog.show_sync(
            model="AI",  # We don't track which model at this point
            tool_call=tool_call,
            permission_level=request.permission_level.value,
            reason=request.description,
        )

        # Handle the response
        if response == PermissionResponse.ALLOW:
            return True
        elif response == PermissionResponse.ALWAYS:
            # Grant permanent permission for this tool
            permissions.set_tool_permission(
                request.tool_name,
                permissions.auto_approve_level,  # Make it auto-approve
            )
            return True
        elif response == PermissionResponse.ALLOW_SESSION:
            # Session permission is automatically granted in check_permission
            # when the callback returns True
            return True
        elif response == PermissionResponse.NEVER:
            # Block this tool
            permissions.block_tool(request.tool_name)
            return False
        else:  # DENY
            return False

    permissions.set_confirmation_callback(confirmation_callback)

    return app
