"""Prompt templates for the orchestration engine.

These templates are used for:
- "Should I speak?" evaluation
- System prompts for each model
- Context summarization
"""

# Template for determining if a model should contribute to the conversation
SHOULD_SPEAK_PROMPT = """You are {model_name} participating in a collaborative group coding chat with other AI assistants ({other_models}).

CURRENT CONVERSATION:
{conversation_history}

USER'S LATEST MESSAGE:
{user_message}

{previous_responses_section}

DECISION CRITERIA - Should you respond?
1. Do you have a genuinely different perspective or approach not yet mentioned?
2. Is there an error, security concern, or important caveat in previous responses?
3. Can you add meaningful technical value beyond what's been said?
4. Were you directly addressed or @mentioned?
5. Does the question touch on your particular strengths?

If other models have already provided excellent, complete answers and you'd just be repeating them, stay SILENT.

Respond with ONLY valid JSON (no markdown, no explanation):
{{"should_speak": true, "confidence": 0.7, "reason": "brief 1-sentence explanation"}}

Rules for confidence:
- 0.9-1.0: You have critical/unique information others missed
- 0.7-0.8: You have a valuable different perspective
- 0.5-0.6: You might add some value but unsure
- 0.3-0.4: Minimal value to add
- 0.0-0.2: Would just be repeating others"""

# Section template for previous responses (only included if there are responses)
PREVIOUS_RESPONSES_TEMPLATE = """RESPONSES FROM OTHER MODELS IN THIS TURN:
{responses}

Note: You're seeing these responses before deciding if you should speak. If they've already covered the topic well, consider staying silent."""

# System prompt template for model responses
SYSTEM_PROMPT_TEMPLATE = """You are {model_name}, an AI assistant in a collaborative coding group chat.

GROUP CHAT CONTEXT:
- Other AI assistants in this chat: {other_models}
- You're part of a team helping users with coding problems
- Each assistant may contribute their perspective
- Responses should be complementary, not redundant

YOUR ROLE:
- Provide your unique perspective and expertise
- Be concise but thorough
- If you agree with another model, add value rather than repeat
- Acknowledge and build upon good points from other models
- Be direct and technical - this is a coding chat

FORMATTING:
- Use markdown for code blocks with language tags
- Keep explanations focused and practical
- Include code examples when helpful"""

# Template for summarizing conversation history when it exceeds context limits
CONTEXT_SUMMARY_PROMPT = """Summarize this conversation history for context in a coding group chat.
Keep:
- Key technical decisions made
- Important code snippets or file references
- Unresolved questions or tasks
- Error messages or issues encountered

Discard:
- Pleasantries and greetings
- Redundant explanations
- Verbose code that can be referenced by filename

CONVERSATION TO SUMMARIZE:
{conversation}

Provide a concise technical summary (aim for 500-1000 tokens):"""


def format_should_speak_prompt(
    model_name: str,
    other_models: list[str],
    conversation_history: str,
    user_message: str,
    previous_responses: list[tuple[str, str]] | None = None,
) -> str:
    """Format the 'should speak?' evaluation prompt.

    Args:
        model_name: Name of the model being evaluated
        other_models: Names of other models in the chat
        conversation_history: Formatted conversation history
        user_message: The user's latest message
        previous_responses: List of (model_name, response) tuples from earlier this turn

    Returns:
        Formatted prompt string
    """
    # Build previous responses section if there are any
    if previous_responses:
        responses_text = "\n\n".join(
            f"[{name}]: {response}" for name, response in previous_responses
        )
        previous_section = PREVIOUS_RESPONSES_TEMPLATE.format(responses=responses_text)
    else:
        previous_section = ""

    return SHOULD_SPEAK_PROMPT.format(
        model_name=model_name,
        other_models=", ".join(other_models),
        conversation_history=conversation_history or "(No previous messages)",
        user_message=user_message,
        previous_responses_section=previous_section,
    )


def format_system_prompt(
    model_name: str,
    other_models: list[str],
    additional_context: str | None = None,
) -> str:
    """Format the system prompt for a model response.

    Args:
        model_name: Name of the model
        other_models: Names of other models in the chat
        additional_context: Optional additional context to include

    Returns:
        Formatted system prompt
    """
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        model_name=model_name,
        other_models=", ".join(other_models),
    )

    if additional_context:
        prompt += f"\n\nADDITIONAL CONTEXT:\n{additional_context}"

    return prompt


def format_context_summary_prompt(conversation: str) -> str:
    """Format the prompt for summarizing conversation context.

    Args:
        conversation: The conversation text to summarize

    Returns:
        Formatted summary prompt
    """
    return CONTEXT_SUMMARY_PROMPT.format(conversation=conversation)
