"""@mention parsing for the orchestrator.

Handles parsing @model mentions from user messages, supporting:
- @claude, @gpt, @gemini, @grok - individual model mentions
- @all - force all models to respond
"""

import re
from typing import NamedTuple

# Known model names that can be mentioned
KNOWN_MODELS = {"claude", "gpt", "gemini", "grok"}

# Pattern to match @mentions (case insensitive)
# Matches @claude, @gpt, @gemini, @grok, @all
MENTION_PATTERN = re.compile(
    r"@(claude|gpt|gemini|grok|all)\b",
    re.IGNORECASE,
)


class ParsedMentions(NamedTuple):
    """Result of parsing mentions from a message."""

    mentions: list[str]  # List of mentioned model names (lowercase)
    clean_message: str  # Message with mentions removed
    force_all: bool  # True if @all was mentioned


def parse_mentions(message: str) -> ParsedMentions:
    """Parse @mentions from a user message.

    Args:
        message: The user's message possibly containing @mentions

    Returns:
        ParsedMentions with extracted mentions and cleaned message

    Examples:
        >>> parse_mentions("@claude what do you think?")
        ParsedMentions(mentions=['claude'], clean_message='what do you think?', force_all=False)

        >>> parse_mentions("@all please help")
        ParsedMentions(mentions=[], clean_message='please help', force_all=True)

        >>> parse_mentions("@gpt @gemini compare approaches")
        ParsedMentions(mentions=['gpt', 'gemini'], clean_message='compare approaches', force_all=False)
    """
    # Find all mentions
    raw_mentions = [m.lower() for m in MENTION_PATTERN.findall(message)]

    # Check for @all
    force_all = "all" in raw_mentions

    # Get individual model mentions (exclude 'all')
    mentions = [m for m in raw_mentions if m in KNOWN_MODELS]

    # Remove duplicates while preserving order
    seen = set()
    unique_mentions = []
    for m in mentions:
        if m not in seen:
            seen.add(m)
            unique_mentions.append(m)

    # Remove mentions from message
    clean = MENTION_PATTERN.sub("", message)
    # Collapse multiple spaces and strip
    clean = re.sub(r"\s+", " ", clean).strip()

    return ParsedMentions(
        mentions=unique_mentions,
        clean_message=clean,
        force_all=force_all,
    )


def get_forced_speakers(
    parsed: ParsedMentions,
    available_models: list[str],
) -> list[str]:
    """Determine which models are forced to speak based on mentions.

    Args:
        parsed: Result from parse_mentions
        available_models: List of available model names

    Returns:
        List of model names that are forced to speak

    Examples:
        >>> parsed = parse_mentions("@claude explain this")
        >>> get_forced_speakers(parsed, ['claude', 'gpt', 'gemini'])
        ['claude']

        >>> parsed = parse_mentions("@all help me")
        >>> get_forced_speakers(parsed, ['claude', 'gpt'])
        ['claude', 'gpt']
    """
    if parsed.force_all:
        return list(available_models)

    # Return mentioned models that are actually available
    return [m for m in parsed.mentions if m in available_models]


def contains_mention(message: str, model_name: str) -> bool:
    """Check if a message contains a mention of a specific model.

    Args:
        message: The message to check
        model_name: The model name to look for

    Returns:
        True if the model is mentioned
    """
    pattern = re.compile(rf"@{model_name}\b", re.IGNORECASE)
    return bool(pattern.search(message))


def contains_any_mention(message: str) -> bool:
    """Check if a message contains any @mentions.

    Args:
        message: The message to check

    Returns:
        True if any mention is found
    """
    return bool(MENTION_PATTERN.search(message))
