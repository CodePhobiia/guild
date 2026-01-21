"""Orchestration engine for CodeCrew multi-model conversations.

This package provides the core orchestration logic that coordinates
multiple AI models in a group chat setting.

Main components:
- Orchestrator: Main engine that coordinates the conversation flow
- PersistentOrchestrator: Orchestrator with automatic persistence
- ToolEnabledOrchestrator: Orchestrator with tool execution support
- SpeakingEvaluator: Determines which models should speak
- TurnManager: Manages speaking order
- ContextAssembler: Builds context windows for each model
- OrchestratorEvent: Events emitted during processing
"""

from .context import ContextAssembler, ContextSummarizer, assemble_context
from .engine import Orchestrator, create_orchestrator
from .events import EventType, OrchestratorEvent, SpeakerDecision
from .mentions import (
    KNOWN_MODELS,
    ParsedMentions,
    contains_any_mention,
    contains_mention,
    get_forced_speakers,
    parse_mentions,
)
from .persistent import PersistentOrchestrator, create_persistent_orchestrator
from .prompts import (
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
from .speaking import (
    DEFAULT_SILENCE_THRESHOLD,
    SpeakingEvaluator,
    evaluate_speakers,
)
from .tool_orchestrator import (
    ToolEnabledOrchestrator,
    create_tool_enabled_orchestrator,
)
from .turns import TurnManager, TurnStrategy, create_turn_manager

__all__ = [
    # Main orchestrator
    "Orchestrator",
    "create_orchestrator",
    # Persistent orchestrator
    "PersistentOrchestrator",
    "create_persistent_orchestrator",
    # Tool-enabled orchestrator
    "ToolEnabledOrchestrator",
    "create_tool_enabled_orchestrator",
    # Events
    "EventType",
    "OrchestratorEvent",
    "SpeakerDecision",
    # Speaking evaluation
    "SpeakingEvaluator",
    "evaluate_speakers",
    "DEFAULT_SILENCE_THRESHOLD",
    # Turn management
    "TurnManager",
    "TurnStrategy",
    "create_turn_manager",
    # Context assembly
    "ContextAssembler",
    "ContextSummarizer",
    "assemble_context",
    # Mentions
    "parse_mentions",
    "get_forced_speakers",
    "contains_mention",
    "contains_any_mention",
    "ParsedMentions",
    "KNOWN_MODELS",
    # Prompts
    "SHOULD_SPEAK_PROMPT",
    "SHOULD_SPEAK_PROMPT_V2",
    "SYSTEM_PROMPT_TEMPLATE",
    "SYSTEM_PROMPT_TEMPLATE_V2",
    "format_should_speak_prompt",
    "format_system_prompt",
    # Model profiles
    "ModelProfile",
    "MODEL_PROFILES",
    "get_model_profile",
]
