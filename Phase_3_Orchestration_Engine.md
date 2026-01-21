# Phase 3: Orchestration Engine

## Phase Overview
- **Duration Estimate**: 5 days
- **Dependencies**: Phase 2 (Model Client Abstraction Layer)
- **Unlocks**: Phase 5 (Tool System), Phase 6 (TUI) - partial
- **Risk Level**: High (core logic complexity)

## Objectives
1. Implement the central orchestration engine that coordinates multi-model conversations
2. Build the "should I speak?" evaluation system with parallel model querying
3. Create turn management logic that handles sequential response generation
4. Design context assembly that respects per-model token limits

## Prerequisites
- [ ] Phase 2 completed - all model clients working
- [ ] At least 2 model clients verified with real API calls
- [ ] Understanding of async patterns in Python

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| Orchestrator class | Code | Coordinates full conversation turn lifecycle |
| Speaking evaluator | Code | Parallel "should speak?" queries return within 3s |
| Turn manager | Code | Handles sequential response generation correctly |
| Context assembler | Code | Builds per-model context respecting token limits |
| @mention parser | Code | Correctly identifies and routes @mentions |
| Response aggregator | Code | Collects and orders all model responses |

## Technical Specifications

### Architecture Decisions
1. **Parallel "Should Speak?" Evaluation**: Query all enabled models simultaneously using `asyncio.gather()` to minimize latency
2. **Sequential Response Generation**: Models that want to speak respond in order (configurable: rotate, fixed, or by confidence)
3. **Conversation History as Source of Truth**: All messages added to history before model sees them
4. **Context Windowing**: Each model gets a tailored context window respecting its token limit
5. **Stateless Orchestrator**: State lives in conversation history, not in orchestrator

### Component Breakdown

#### Orchestrator Engine (`codecrew/orchestrator/engine.py`)
- **Purpose**: Main coordination point for processing user messages and generating responses
- **Location**: `codecrew/orchestrator/engine.py`
- **Interfaces**:
  ```python
  class Orchestrator:
      def __init__(
          self,
          clients: Dict[str, ModelClient],
          conversation: ConversationManager,
          settings: Settings,
      ): ...
      
      async def process_message(
          self,
          user_message: str,
      ) -> AsyncIterator[OrchestratorEvent]: ...
      
      async def process_with_mentions(
          self,
          user_message: str,
          mentions: List[str],
      ) -> AsyncIterator[OrchestratorEvent]: ...
      
      async def retry_model(
          self,
          model_name: str,
      ) -> AsyncIterator[OrchestratorEvent]: ...
  ```
- **Implementation Notes**: 
  - Yields events (thinking, speaking, response, error, silent) for UI to render
  - Handles @mentions as forced speakers
  - Supports retry of individual models

#### Speaking Evaluator (`codecrew/orchestrator/speaking.py`)
- **Purpose**: Determines which models should contribute to conversation
- **Location**: `codecrew/orchestrator/speaking.py`
- **Interfaces**:
  ```python
  class SpeakingEvaluator:
      def __init__(
          self,
          clients: Dict[str, ModelClient],
          silence_threshold: float = 0.3,
      ): ...
      
      async def evaluate_all(
          self,
          conversation: List[Message],
          user_message: str,
          previous_responses: List[ModelResponse],
          forced_speakers: Optional[List[str]] = None,
      ) -> List[SpeakerDecision]: ...
  ```
- **Implementation Notes**:
  - Uses the "Should I Speak?" prompt template from PRD
  - Returns decisions sorted by confidence
  - Handles @all forcing all to speak

#### Context Assembler (`codecrew/orchestrator/context.py`)
- **Purpose**: Build appropriate context windows for each model
- **Location**: `codecrew/orchestrator/context.py`
- **Interfaces**:
  ```python
  class ContextAssembler:
      def __init__(
          self,
          max_tokens: int = 100000,
      ): ...
      
      def assemble_for_model(
          self,
          conversation: List[Message],
          model: ModelClient,
          pinned_ids: Set[str],
          include_system: bool = True,
      ) -> List[Message]: ...
      
      def estimate_tokens(
          self,
          messages: List[Message],
          model: ModelClient,
      ) -> int: ...
  ```
- **Implementation Notes**:
  - Prioritizes: system message > pinned messages > recent messages
  - Uses sliding window with smart truncation
  - Generates summary for very long conversations

#### Turn Manager (`codecrew/orchestrator/turns.py`)
- **Purpose**: Manage speaking order and sequential response generation
- **Location**: `codecrew/orchestrator/turns.py`
- **Interfaces**:
  ```python
  class TurnManager:
      def __init__(
          self,
          strategy: Literal["rotate", "confidence", "fixed"],
          fixed_order: Optional[List[str]] = None,
      ): ...
      
      def determine_order(
          self,
          decisions: List[SpeakerDecision],
      ) -> List[str]: ...
      
      def get_first_responder(self) -> str: ...
      
      def rotate_first_responder(self) -> None: ...
  ```

### Data Models / Schemas

#### Orchestrator Events
```python
from dataclasses import dataclass
from enum import Enum, auto

class EventType(Enum):
    THINKING = auto()      # Model is evaluating whether to speak
    WILL_SPEAK = auto()    # Model decided to speak
    WILL_STAY_SILENT = auto()  # Model decided to stay silent
    RESPONSE_START = auto()    # Starting to generate response
    RESPONSE_CHUNK = auto()    # Streaming chunk
    RESPONSE_COMPLETE = auto() # Full response ready
    TOOL_CALL = auto()         # Model wants to call a tool
    TOOL_RESULT = auto()       # Tool execution completed
    ERROR = auto()             # Error occurred
    TURN_COMPLETE = auto()     # All models done for this turn

@dataclass
class OrchestratorEvent:
    type: EventType
    model: Optional[str] = None
    content: Optional[str] = None
    response: Optional[ModelResponse] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    error: Optional[str] = None

@dataclass
class SpeakerDecision:
    model: str
    should_speak: bool
    confidence: float
    reason: str
    is_forced: bool = False  # True if @mentioned
```

## Implementation Tasks

### Task Group: Core Orchestrator
- [ ] **[TASK-3.1]** Implement OrchestratorEvent types
  - Files: `codecrew/orchestrator/events.py`
  - Details: Define all event types and dataclasses
  - Estimate: 1 hour

- [ ] **[TASK-3.2]** Create Orchestrator class skeleton
  - Files: `codecrew/orchestrator/engine.py`
  - Details:
    ```python
    class Orchestrator:
        def __init__(
            self,
            clients: Dict[str, ModelClient],
            conversation: ConversationManager,
            settings: Settings,
        ):
            self.clients = clients
            self.conversation = conversation
            self.settings = settings
            self.speaking_evaluator = SpeakingEvaluator(
                clients, 
                settings.conversation.silence_threshold
            )
            self.turn_manager = TurnManager(
                settings.conversation.first_responder
            )
            self.context_assembler = ContextAssembler(
                settings.conversation.max_context_tokens
            )
    ```
  - Estimate: 1.5 hours

- [ ] **[TASK-3.3]** Implement main process_message flow
  - Files: `codecrew/orchestrator/engine.py`
  - Details:
    ```python
    async def process_message(
        self,
        user_message: str,
    ) -> AsyncIterator[OrchestratorEvent]:
        # 1. Parse for @mentions
        mentions, clean_message = self._parse_mentions(user_message)
        
        # 2. Add user message to conversation history
        await self.conversation.add_message(
            role="user",
            content=clean_message,
        )
        
        # 3. Evaluate who should speak
        yield OrchestratorEvent(type=EventType.THINKING)
        decisions = await self.speaking_evaluator.evaluate_all(
            conversation=await self.conversation.get_messages(),
            user_message=clean_message,
            previous_responses=[],
            forced_speakers=mentions,
        )
        
        # 4. Announce speaking intentions
        for decision in decisions:
            event_type = (
                EventType.WILL_SPEAK 
                if decision.should_speak 
                else EventType.WILL_STAY_SILENT
            )
            yield OrchestratorEvent(
                type=event_type,
                model=decision.model,
            )
        
        # 5. Generate responses sequentially
        speakers = self.turn_manager.determine_order(decisions)
        previous_responses = []
        
        for model_name in speakers:
            async for event in self._generate_model_response(
                model_name, 
                previous_responses
            ):
                yield event
                if event.type == EventType.RESPONSE_COMPLETE:
                    previous_responses.append(event.response)
        
        # 6. Complete turn
        yield OrchestratorEvent(type=EventType.TURN_COMPLETE)
    ```
  - Estimate: 3 hours

- [ ] **[TASK-3.4]** Implement _generate_model_response helper
  - Files: `codecrew/orchestrator/engine.py`
  - Details: Handle streaming, tool calls, error recovery for single model
  - Estimate: 2.5 hours

### Task Group: Speaking Evaluation
- [ ] **[TASK-3.5]** Create "Should I Speak?" prompt template
  - Files: `codecrew/orchestrator/prompts.py`
  - Details:
    ```python
    SHOULD_SPEAK_PROMPT = """You are {model_name} in a group coding chat with other AI assistants.

    Current conversation:
    {conversation_history}

    The user's latest message:
    {user_message}

    Other models that have already responded:
    {previous_responses}

    Should you respond? Consider:
    1. Do you have a genuinely different perspective?
    2. Is there an error or important caveat to address?
    3. Can you add meaningful value beyond what's been said?
    4. Were you directly addressed or @mentioned?

    Respond with JSON only:
    {{"should_speak": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""
    ```
  - Estimate: 1 hour

- [ ] **[TASK-3.6]** Implement SpeakingEvaluator class
  - Files: `codecrew/orchestrator/speaking.py`
  - Details:
    ```python
    class SpeakingEvaluator:
        async def evaluate_all(
            self,
            conversation: List[Message],
            user_message: str,
            previous_responses: List[ModelResponse],
            forced_speakers: Optional[List[str]] = None,
        ) -> List[SpeakerDecision]:
            forced = set(forced_speakers or [])
            force_all = "@all" in forced
            
            # Query all models in parallel
            tasks = [
                self._evaluate_single(
                    model_name,
                    client,
                    conversation,
                    user_message,
                    previous_responses,
                    is_forced=(model_name in forced or force_all),
                )
                for model_name, client in self.clients.items()
            ]
            
            decisions = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions gracefully
            results = []
            for decision in decisions:
                if isinstance(decision, Exception):
                    logger.error(f"Evaluation failed: {decision}")
                else:
                    results.append(decision)
            
            return sorted(results, key=lambda d: d.confidence, reverse=True)
    ```
  - Estimate: 2.5 hours

- [ ] **[TASK-3.7]** Implement JSON response parsing with fallbacks
  - Files: `codecrew/orchestrator/speaking.py`
  - Details: Handle malformed JSON, missing fields, timeout
  - Estimate: 1.5 hours

### Task Group: Context Assembly
- [ ] **[TASK-3.8]** Implement ContextAssembler class
  - Files: `codecrew/orchestrator/context.py`
  - Details:
    ```python
    class ContextAssembler:
        def assemble_for_model(
            self,
            conversation: List[Message],
            model: ModelClient,
            pinned_ids: Set[str],
            include_system: bool = True,
        ) -> List[Message]:
            max_tokens = self.max_tokens
            result = []
            current_tokens = 0
            
            # 1. Always include system message first
            if include_system:
                system_msg = self._get_system_message(model)
                result.append(system_msg)
                current_tokens += model.count_tokens(system_msg.content)
            
            # 2. Add pinned messages
            for msg in conversation:
                if msg.id in pinned_ids:
                    tokens = model.count_tokens(msg.content)
                    if current_tokens + tokens < max_tokens:
                        result.append(msg)
                        current_tokens += tokens
            
            # 3. Fill remaining with recent messages (most recent first)
            for msg in reversed(conversation):
                if msg.id in pinned_ids:
                    continue
                tokens = model.count_tokens(msg.content)
                if current_tokens + tokens < max_tokens:
                    result.insert(-len(result) or len(result), msg)
                    current_tokens += tokens
                else:
                    break
            
            return result
    ```
  - Estimate: 2.5 hours

- [ ] **[TASK-3.9]** Implement context summarization for overflow
  - Files: `codecrew/orchestrator/context.py`
  - Details: When context exceeds limits, generate summary of older messages
  - Estimate: 2 hours

### Task Group: Turn Management
- [ ] **[TASK-3.10]** Implement TurnManager class
  - Files: `codecrew/orchestrator/turns.py`
  - Details:
    ```python
    class TurnManager:
        def __init__(
            self,
            strategy: str = "rotate",
            fixed_order: Optional[List[str]] = None,
        ):
            self.strategy = strategy
            self.fixed_order = fixed_order or ["claude", "gpt", "gemini", "grok"]
            self.rotation_index = 0
        
        def determine_order(
            self,
            decisions: List[SpeakerDecision],
        ) -> List[str]:
            speakers = [d.model for d in decisions if d.should_speak]
            
            if self.strategy == "confidence":
                # Already sorted by confidence
                return speakers
            elif self.strategy == "rotate":
                # Start with current first responder, maintain relative order
                first = self.fixed_order[self.rotation_index]
                ordered = self._order_from_start(speakers, first)
                self.rotate_first_responder()
                return ordered
            else:
                # Fixed order
                return [m for m in self.fixed_order if m in speakers]
    ```
  - Estimate: 1.5 hours

### Task Group: @Mention Parsing
- [ ] **[TASK-3.11]** Implement mention parser
  - Files: `codecrew/orchestrator/mentions.py`
  - Details:
    ```python
    import re
    
    MENTION_PATTERN = re.compile(r'@(claude|gpt|gemini|grok|all)\b', re.IGNORECASE)
    
    def parse_mentions(message: str) -> tuple[List[str], str]:
        """Parse @mentions from message, return (mentions, clean_message)."""
        mentions = [m.lower() for m in MENTION_PATTERN.findall(message)]
        clean = MENTION_PATTERN.sub('', message).strip()
        clean = re.sub(r'\s+', ' ', clean)  # Collapse whitespace
        return mentions, clean
    ```
  - Estimate: 1 hour

### Task Group: Integration and Testing
- [ ] **[TASK-3.12]** Create orchestrator __init__.py with exports
  - Files: `codecrew/orchestrator/__init__.py`
  - Details: Export Orchestrator, all event types
  - Estimate: 0.5 hours

- [ ] **[TASK-3.13]** Write unit tests for mention parsing
  - Files: `tests/test_orchestrator/test_mentions.py`
  - Details: Test various @mention patterns, edge cases
  - Estimate: 1 hour

- [ ] **[TASK-3.14]** Write unit tests for speaking evaluator
  - Files: `tests/test_orchestrator/test_speaking.py`
  - Details: Test with mock clients, parallel evaluation, timeout handling
  - Estimate: 2 hours

- [ ] **[TASK-3.15]** Write unit tests for context assembler
  - Files: `tests/test_orchestrator/test_context.py`
  - Details: Test token limits, pinned messages, priority ordering
  - Estimate: 2 hours

- [ ] **[TASK-3.16]** Write integration tests for full orchestrator flow
  - Files: `tests/test_orchestrator/test_engine.py`
  - Details: Test complete message processing with mock clients
  - Estimate: 3 hours

## Testing Requirements

### Unit Tests
- [ ] Mention parser extracts all mention types (@claude, @gpt, @all, etc.)
- [ ] Mention parser handles case insensitivity
- [ ] Mention parser returns clean message without mentions
- [ ] Speaking evaluator queries all models in parallel
- [ ] Speaking evaluator handles model failures gracefully
- [ ] Speaking evaluator respects forced speakers from @mentions
- [ ] Context assembler respects token limits
- [ ] Context assembler prioritizes pinned messages
- [ ] Context assembler includes system message first
- [ ] Turn manager orders by confidence when configured
- [ ] Turn manager rotates first responder correctly

### Integration Tests
- [ ] Full message processing yields all expected events
- [ ] Events yield in correct order (THINKING → WILL_SPEAK → RESPONSE → COMPLETE)
- [ ] Multiple models can respond to single user message
- [ ] @all forces all models to respond
- [ ] Single @mention forces only that model
- [ ] Conversation history grows with each turn
- [ ] Error in one model doesn't crash entire turn

### Manual Verification
- [ ] Send message and observe thinking indicators
- [ ] Verify models make intelligent silence decisions
- [ ] Check that @claude forces Claude to respond
- [ ] Test @all to see all models respond
- [ ] Verify responses reference each other's content

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All tests passing
- [ ] Orchestrator correctly coordinates multi-model conversations
- [ ] "Should speak?" evaluations complete within 3 seconds
- [ ] Context assembly respects model token limits
- [ ] @mention routing works correctly
- [ ] Code formatted and linted
- [ ] Type hints complete

## Rollback Plan
The orchestrator is the core of the system. If issues arise:

1. **Simplify to single model**: Bypass speaking evaluation, always use one model
2. **Disable parallel evaluation**: Query models sequentially
3. **Reduce context complexity**: Use simpler FIFO context without priorities

Recovery approach:
1. Identify which component is failing (evaluator, context, turns)
2. Add extensive logging to trace issue
3. Simplify that component while maintaining interfaces

## Notes & Considerations

### Edge Cases
- All models decide to stay silent
- First model errors, subsequent models succeed
- User sends empty message
- Very long user message exceeds all context limits
- "Should speak?" evaluation times out
- Model returns invalid JSON for should_speak

### Known Limitations
- No support for models responding to each other (inter-model dialogue) in v1
- Context summarization is basic (could use dedicated model)
- No streaming for "should speak?" evaluation

### Future Improvements
- Inter-model dialogue (models can @mention each other)
- Smarter context summarization using AI
- Confidence-based response ordering
- Caching "should speak?" decisions for similar contexts
- Parallel response generation (complex ordering issues)

### Performance Considerations
- "Should speak?" adds ~2-3 seconds latency per turn
- Consider caching system prompts
- Monitor memory usage with long conversations
- May need to batch tool results for efficiency
