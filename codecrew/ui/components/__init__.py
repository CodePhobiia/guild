"""TUI components for CodeCrew.

This package contains the visual components used in the terminal interface.
"""

from codecrew.ui.components.header import CompactHeader, Header
from codecrew.ui.components.input_area import InputArea, MentionCompleter, SimpleInput
from codecrew.ui.components.message import (
    DecisionIndicator,
    MessageRenderer,
    StreamingMessage,
)
from codecrew.ui.components.message_list import MessageItem, MessageList
from codecrew.ui.components.spinner import (
    Spinner,
    SpinnerType,
    ThinkingIndicator,
    ToolExecutingIndicator,
    TypingIndicator,
)
from codecrew.ui.components.status_bar import MiniStatus, StatusBar
from codecrew.ui.components.tool_panel import (
    PermissionRequestDisplay,
    ToolCallDisplay,
    ToolPanel,
)

__all__ = [
    # Header
    "Header",
    "CompactHeader",
    # Input
    "InputArea",
    "MentionCompleter",
    "SimpleInput",
    # Messages
    "MessageRenderer",
    "StreamingMessage",
    "DecisionIndicator",
    "MessageItem",
    "MessageList",
    # Spinner
    "Spinner",
    "SpinnerType",
    "ThinkingIndicator",
    "TypingIndicator",
    "ToolExecutingIndicator",
    # Status
    "StatusBar",
    "MiniStatus",
    # Tools
    "ToolPanel",
    "ToolCallDisplay",
    "PermissionRequestDisplay",
]
