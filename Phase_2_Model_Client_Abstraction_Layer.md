# Phase 2: Model Client Abstraction Layer

## Phase Overview
- **Duration Estimate**: 4 days
- **Dependencies**: Phase 1 (Foundation & Project Setup)
- **Unlocks**: Phase 3 (Orchestration Engine)
- **Risk Level**: Medium (API differences between providers)

## Objectives
1. Create a unified `ModelClient` abstract base class that normalizes interaction across all AI providers
2. Implement working clients for all four models: Claude, GPT, Gemini, and Grok
3. Support streaming responses with consistent event handling
4. Handle API authentication, rate limiting basics, and error classification

## Prerequisites
- [ ] Phase 1 completed - project structure and config system in place
- [ ] API keys configured for at least Claude and OpenAI
- [ ] Understanding of each provider's API and SDK

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| `ModelClient` ABC | Code | Abstract base class with all required methods defined |
| `ClaudeClient` | Code | Working integration with Anthropic API, streaming support |
| `GPTClient` | Code | Working integration with OpenAI API, streaming support |
| `GeminiClient` | Code | Working integration with Google Generative AI, streaming support |
| `GrokClient` | Code | Working integration with xAI API (or mock if unavailable) |
| Model registry | Code | Factory function to instantiate clients by name |
| Response models | Code | Unified response types across all providers |

## Technical Specifications

### Architecture Decisions
1. **Unified Response Format**: All clients return the same response structures regardless of provider differences
2. **Async-First**: All API calls are async to support parallel "should I speak?" evaluations
3. **Streaming Abstraction**: Use async generators for streaming, hiding provider-specific implementations
4. **Graceful Degradation**: If a model fails, the system continues with available models
5. **Tool Format Translation**: Each client handles translating unified tool definitions to provider format

### Data Models / Schemas

#### Unified Response Types
```python
from dataclasses import dataclass, field
from typing import Optional, List, AsyncIterator
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False

@dataclass
class Message:
    role: MessageRole
    content: str
    model: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)

@dataclass
class ModelResponse:
    content: str
    model: str
    finish_reason: str  # 'stop', 'tool_use', 'length', 'error'
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Optional[dict] = None  # tokens, cost estimate

@dataclass
class StreamChunk:
    content: str
    is_complete: bool = False
    tool_call: Optional[ToolCall] = None

@dataclass
class ShouldSpeakResult:
    should_speak: bool
    confidence: float
    reason: str
```

#### Tool Definition Schema
```python
@dataclass
class ToolParameter:
    name: str
    type: str  # 'string', 'integer', 'boolean', 'array', 'object'
    description: str
    required: bool = True
    enum: Optional[List[str]] = None

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: List[ToolParameter]
    
    def to_anthropic(self) -> dict: ...
    def to_openai(self) -> dict: ...
    def to_google(self) -> dict: ...
    def to_xai(self) -> dict: ...
```

### Component Breakdown

#### ModelClient ABC (`codecrew/models/base.py`)
- **Purpose**: Define the contract all model clients must implement
- **Location**: `codecrew/models/base.py`
- **Interfaces**:
  ```python
  from abc import ABC, abstractmethod
  
  class ModelClient(ABC):
      name: str  # 'claude', 'gpt', 'gemini', 'grok'
      display_name: str  # 'Claude', 'GPT', etc.
      color: str  # Hex color for UI
      
      @abstractmethod
      async def generate(
          self,
          messages: List[Message],
          tools: Optional[List[ToolDefinition]] = None,
          max_tokens: int = 4096,
          temperature: float = 0.7,
      ) -> ModelResponse: ...
      
      @abstractmethod
      async def generate_stream(
          self,
          messages: List[Message],
          tools: Optional[List[ToolDefinition]] = None,
          max_tokens: int = 4096,
          temperature: float = 0.7,
      ) -> AsyncIterator[StreamChunk]: ...
      
      @abstractmethod
      async def should_speak(
          self,
          conversation: List[Message],
          user_message: str,
          previous_responses: List[ModelResponse],
      ) -> ShouldSpeakResult: ...
      
      @abstractmethod
      def count_tokens(self, text: str) -> int: ...
      
      @property
      @abstractmethod
      def is_available(self) -> bool: ...
  ```
- **Implementation Notes**: Include helper methods for common operations

#### ClaudeClient (`codecrew/models/claude.py`)
- **Purpose**: Anthropic Claude API integration
- **Location**: `codecrew/models/claude.py`
- **Implementation Notes**:
  - Use official `anthropic` SDK
  - Native tool use support
  - Streaming via `client.messages.stream()`
  - Token counting via `anthropic.count_tokens()`

#### GPTClient (`codecrew/models/gpt.py`)
- **Purpose**: OpenAI GPT API integration
- **Location**: `codecrew/models/gpt.py`
- **Implementation Notes**:
  - Use official `openai` SDK
  - Function calling maps to tool definitions
  - Streaming via `stream=True` parameter
  - Token counting via `tiktoken` library

#### GeminiClient (`codecrew/models/gemini.py`)
- **Purpose**: Google Gemini API integration
- **Location**: `codecrew/models/gemini.py`
- **Implementation Notes**:
  - Use `google-generativeai` SDK
  - Function declarations for tools
  - Streaming via `generate_content_stream()`
  - Different message format (Content, Parts)

#### GrokClient (`codecrew/models/grok.py`)
- **Purpose**: xAI Grok API integration
- **Location**: `codecrew/models/grok.py`
- **Implementation Notes**:
  - xAI API follows OpenAI format (use similar implementation)
  - May need to use httpx directly if no official SDK
  - Implement mock mode for development if API unavailable

#### Model Registry (`codecrew/models/__init__.py`)
- **Purpose**: Factory for creating model clients, central access point
- **Location**: `codecrew/models/__init__.py`
- **Interfaces**:
  ```python
  def get_client(name: str, config: ModelConfig) -> ModelClient: ...
  def get_all_clients(settings: Settings) -> Dict[str, ModelClient]: ...
  def get_enabled_clients(settings: Settings) -> Dict[str, ModelClient]: ...
  ```

## Implementation Tasks

### Task Group: Base Infrastructure
- [ ] **[TASK-2.1]** Create unified message and response types
  - Files: `codecrew/models/types.py`
  - Details: Define all dataclasses for Message, ModelResponse, StreamChunk, etc.
  - Estimate: 1.5 hours

- [ ] **[TASK-2.2]** Create tool definition schema with provider translations
  - Files: `codecrew/models/tools.py`
  - Details: ToolDefinition class with to_anthropic(), to_openai(), to_google(), to_xai() methods
  - Estimate: 2 hours

- [ ] **[TASK-2.3]** Implement ModelClient abstract base class
  - Files: `codecrew/models/base.py`
  - Details: 
    - Abstract methods for generate, generate_stream, should_speak
    - Concrete helper methods for common operations
    - Error handling patterns
  - Estimate: 2 hours

### Task Group: Claude Implementation
- [ ] **[TASK-2.4]** Implement ClaudeClient class
  - Files: `codecrew/models/claude.py`
  - Details:
    ```python
    class ClaudeClient(ModelClient):
        name = "claude"
        display_name = "Claude"
        color = "#E07B53"
        
        def __init__(self, config: ModelConfig):
            self.client = anthropic.AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            self.model_id = config.model_id
            self.max_tokens = config.max_tokens
            self.temperature = config.temperature
        
        async def generate(self, messages, tools=None, **kwargs):
            # Translate messages to Anthropic format
            # Handle tool definitions
            # Make API call
            # Translate response to ModelResponse
            ...
    ```
  - Estimate: 3 hours

- [ ] **[TASK-2.5]** Implement Claude streaming support
  - Files: `codecrew/models/claude.py`
  - Details: Use `with client.messages.stream() as stream` pattern
  - Estimate: 1.5 hours

- [ ] **[TASK-2.6]** Implement Claude "should speak" evaluation
  - Files: `codecrew/models/claude.py`
  - Details: Format the meta-prompt, parse JSON response
  - Estimate: 1 hour

### Task Group: GPT Implementation
- [ ] **[TASK-2.7]** Implement GPTClient class
  - Files: `codecrew/models/gpt.py`
  - Details:
    ```python
    class GPTClient(ModelClient):
        name = "gpt"
        display_name = "GPT"
        color = "#10A37F"
        
        def __init__(self, config: ModelConfig):
            self.client = openai.AsyncOpenAI(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            ...
    ```
  - Estimate: 2.5 hours

- [ ] **[TASK-2.8]** Implement GPT streaming support
  - Files: `codecrew/models/gpt.py`
  - Details: Handle delta chunks, function call streaming
  - Estimate: 1.5 hours

- [ ] **[TASK-2.9]** Add tiktoken for GPT token counting
  - Files: `codecrew/models/gpt.py`
  - Details: Install tiktoken, implement count_tokens using appropriate encoding
  - Estimate: 1 hour

### Task Group: Gemini Implementation
- [ ] **[TASK-2.10]** Implement GeminiClient class
  - Files: `codecrew/models/gemini.py`
  - Details:
    ```python
    class GeminiClient(ModelClient):
        name = "gemini"
        display_name = "Gemini"
        color = "#4285F4"
        
        def __init__(self, config: ModelConfig):
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
            self.model = genai.GenerativeModel(config.model_id)
            ...
    ```
  - Estimate: 3 hours

- [ ] **[TASK-2.11]** Implement Gemini message format translation
  - Files: `codecrew/models/gemini.py`
  - Details: Translate between unified Message format and Gemini's Content/Parts
  - Estimate: 1.5 hours

- [ ] **[TASK-2.12]** Implement Gemini streaming support
  - Files: `codecrew/models/gemini.py`
  - Details: Handle generate_content_async with stream=True
  - Estimate: 1.5 hours

### Task Group: Grok Implementation
- [ ] **[TASK-2.13]** Research xAI API and implement GrokClient
  - Files: `codecrew/models/grok.py`
  - Details:
    - xAI uses OpenAI-compatible API format
    - Use httpx with base_url pointed to xAI endpoint
    - If API not available, implement MockGrokClient for development
  - Estimate: 3 hours

- [ ] **[TASK-2.14]** Implement Grok fallback/mock mode
  - Files: `codecrew/models/grok.py`
  - Details: When API unavailable, return canned responses for testing
  - Estimate: 1 hour

### Task Group: Registry and Integration
- [ ] **[TASK-2.15]** Implement model registry
  - Files: `codecrew/models/__init__.py`
  - Details:
    ```python
    MODEL_CLIENTS = {
        "claude": ClaudeClient,
        "gpt": GPTClient,
        "gemini": GeminiClient,
        "grok": GrokClient,
    }
    
    def get_client(name: str, config: ModelConfig) -> ModelClient:
        if name not in MODEL_CLIENTS:
            raise ValueError(f"Unknown model: {name}")
        return MODEL_CLIENTS[name](config)
    
    def get_enabled_clients(settings: Settings) -> Dict[str, ModelClient]:
        clients = {}
        for name, config in settings.models.items():
            if config.enabled:
                try:
                    clients[name] = get_client(name, config)
                except Exception as e:
                    logger.warning(f"Failed to initialize {name}: {e}")
        return clients
    ```
  - Estimate: 1 hour

- [ ] **[TASK-2.16]** Add retry logic with exponential backoff
  - Files: `codecrew/models/base.py`
  - Details: Decorator for API calls with configurable retry count and backoff
  - Estimate: 1.5 hours

### Task Group: Testing
- [ ] **[TASK-2.17]** Create mock API responses for testing
  - Files: `tests/fixtures/api_responses.py`
  - Details: Fixture data mimicking real API responses for all providers
  - Estimate: 2 hours

- [ ] **[TASK-2.18]** Write unit tests for all model clients
  - Files: `tests/test_models/test_*.py`
  - Details: Test message translation, response parsing, error handling
  - Estimate: 3 hours

- [ ] **[TASK-2.19]** Write integration tests with real APIs (skippable)
  - Files: `tests/test_models/test_integration.py`
  - Details: Marked with `@pytest.mark.integration`, requires API keys
  - Estimate: 2 hours

## Testing Requirements

### Unit Tests
- [ ] Message format correctly translated for each provider
- [ ] Tool definitions correctly converted to provider format
- [ ] Streaming chunks correctly parsed and yielded
- [ ] "Should speak" response correctly parsed from JSON
- [ ] Token counting returns reasonable estimates
- [ ] Error responses correctly classified (rate limit, auth, server error)
- [ ] Retry logic triggers on appropriate error codes
- [ ] Mock mode works when API key not configured

### Integration Tests
- [ ] Simple message generates response from each provider
- [ ] Streaming returns incremental chunks
- [ ] Tool calls are correctly formatted in response
- [ ] "Should speak" returns valid JSON with required fields
- [ ] Rate limit errors trigger appropriate backoff

### Manual Verification
- [ ] Each client can send a simple "Hello" and receive response
- [ ] Streaming displays characters incrementally
- [ ] Tool calls appear in response when tools provided
- [ ] Model registry returns only enabled models
- [ ] Graceful error when API key missing

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All unit tests passing
- [ ] At least 2 models verified with real API calls
- [ ] Mock mode working for all clients
- [ ] Error handling comprehensive
- [ ] Code formatted and linted
- [ ] Type hints complete for public interfaces

## Rollback Plan
If critical issues with a specific provider:
1. Disable that model in config (`enabled: false`)
2. System continues with remaining models
3. Return to provider-specific implementation for fixes

If fundamental design issues:
1. Re-evaluate the unified response format
2. Consider provider-specific response types with adapter pattern
3. May need to adjust orchestrator expectations in Phase 3

## Notes & Considerations

### Edge Cases
- API returns empty content
- Streaming connection dropped mid-response
- Tool call with malformed arguments
- "Should speak" returns non-JSON
- Token count exceeds model's context limit
- Concurrent requests to same provider

### Known Limitations
- xAI/Grok may have limited documentation or API access
- Token counting is approximate for some providers
- No support for vision/multimodal in v1

### Future Improvements
- Add support for local LLMs (Ollama, llama.cpp)
- Implement proper token counting with provider APIs
- Add vision capability for supported models
- Implement response caching for identical requests
- Add cost tracking per request

### Provider-Specific Quirks

**Claude:**
- System message must be first and separate from messages
- Tool results must immediately follow tool use

**GPT:**
- Function calling uses different schema than newer tools
- Parallel function calls possible

**Gemini:**
- Uses Content/Parts structure
- Different safety settings API
- Multi-turn requires specific format

**Grok:**
- OpenAI-compatible but may have subtle differences
- Real-time knowledge claim needs verification
