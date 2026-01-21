# Product Requirements Document: CodeCrew

## AI Coding Groupchat CLI

**Version:** 1.0  
**Author:** Theyab  
**Date:** January 2026

---

## Executive Summary

CodeCrew is a CLI-based AI coding assistant that simulates a group chat environment with multiple AI models: Claude Code, GPT Codex, Gemini 3 Pro, and Grok Code. Unlike traditional single-model coding assistants, CodeCrew enables organic, collaborative conversations where AI models can debate approaches, build on each other's ideas, critique solutions, and collectively solve coding problems—mimicking the dynamics of a developer friend group chat.

---

## Problem Statement

Current AI coding assistants operate in isolation. Developers get one perspective, one coding style, one set of potential blind spots. When facing complex architectural decisions, debugging tricky issues, or exploring implementation approaches, having multiple expert opinions leads to better outcomes.

Developers currently need to:
- Switch between different AI tools manually
- Copy-paste context between interfaces
- Mentally synthesize different perspectives
- Lose conversational continuity across tools

CodeCrew solves this by bringing multiple AI coding experts into a single, persistent conversation.

---

## Product Vision

A CLI tool that feels like opening a group chat with your smartest developer friends—except they're AI models with different strengths, perspectives, and personalities. You ask a question, and the conversation flows naturally. Models contribute when they have something valuable to add, stay silent when they don't, and can be called upon directly when you want a specific perspective.

---

## Core Features

### 1. Multi-Model Groupchat

**1.1 Participating Models**
- Claude Code (Anthropic)
- GPT Codex (OpenAI)
- Gemini 3 Pro (Google)
- Grok Code (xAI)

**1.2 Conversation Dynamics**
- **Sequential responses:** Models see and can respond to what others have said
- **Voluntary participation:** Models decide if they have something valuable to contribute
- **@mention support:** Force a specific model to respond with `@claude`, `@gpt`, `@gemini`, `@grok`, or `@all`
- **Inter-model dialogue:** Models can address each other, debate, agree, build on ideas
- **Natural silence:** Models that have nothing to add stay quiet (no forced responses)

**1.3 Speaking Logic**
Each model receives the full conversation context and a meta-prompt:
```
You're in a group coding chat with other AI assistants and a developer. 
Only respond if you have:
- A genuinely different approach or perspective
- A correction or important caveat to what was said
- Additional context that adds value
- A direct answer to a question aimed at you

It's completely fine to stay silent. Don't repeat what others said.
If you choose to speak, be concise and additive.
```

**1.4 Turn Order**
- On new user messages: Models evaluate in parallel, responses rendered sequentially based on who "wants" to speak
- Configurable first-responder rotation or fixed order
- Models responding to each other follow natural conversation flow

---

### 2. Standard AI Coding CLI Capabilities

**2.1 File System Operations**
- Read files and directories
- Write/create files
- Edit existing files (with diff preview)
- Delete files (with confirmation)
- Search within files (grep-like)
- Tree view of project structure

**2.2 Code Intelligence**
- Syntax-aware code editing
- Multi-file refactoring
- Dependency analysis
- Import/export management
- Code generation with context awareness

**2.3 Terminal/Shell Integration**
- Execute shell commands
- View command output in real-time
- Background process management
- Environment variable access

**2.4 Git Integration**
- Status, diff, log viewing
- Commit with generated messages
- Branch operations
- Conflict resolution assistance

**2.5 Project Understanding**
- Automatic project type detection
- Framework-specific knowledge
- Config file parsing
- Dependency graph awareness

---

### 3. Conversation Persistence

**3.1 Session Management**
- Auto-save conversations with unique IDs
- Resume with `codecrew --resume` (last session) or `codecrew --resume <session-id>`
- List past sessions with `codecrew --sessions`
- Fresh start is default behavior

**3.2 Conversation Storage**
- Local SQLite database for conversation history
- Stores: messages, model responses, file operations, timestamps
- Searchable history: `codecrew --search "authentication bug"`
- Export conversations: `codecrew --export <session-id> [--format md|json]`

**3.3 Context Windows**
- Smart context management per model (respecting token limits)
- Sliding window with priority retention (recent + pinned messages)
- Ability to "pin" important context: `/pin` command
- Context summary generation for long conversations

---

### 4. User Interface (TUI)

**4.1 Layout**
```
┌─────────────────────────────────────────────────────────────────┐
│ CodeCrew v1.0 | Session: abc123 | Project: ~/myapp              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─ You ──────────────────────────────────────────────────────┐ │
│ │ How should I handle authentication in this Express app?    │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─ Claude ───────────────────────────────────────────────────┐ │
│ │ I'd recommend using Passport.js with JWT strategy. Here's  │ │
│ │ a basic setup:                                             │ │
│ │                                                            │ │
│ │ ```javascript                                              │ │
│ │ const passport = require('passport');                      │ │
│ │ const JwtStrategy = require('passport-jwt').Strategy;      │ │
│ │ ```                                                        │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─ Gemini ───────────────────────────────────────────────────┐ │
│ │ Claude's approach is solid. One addition: consider using   │ │
│ │ refresh tokens for better security. Also, if you're on     │ │
│ │ Express 5, the async error handling is cleaner.            │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ── GPT is silent ──                                             │
│ ── Grok is silent ──                                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [@claude @gpt @gemini @grok @all] [/help for commands]          │
│ > _                                                             │
└─────────────────────────────────────────────────────────────────┘
```

**4.2 Visual Design (using `rich` library)**
- Distinct colors per model:
  - Claude: Orange/Coral (#E07B53)
  - GPT: Green (#10A37F)  
  - Gemini: Blue (#4285F4)
  - Grok: Purple (#7C3AED)
  - User: White/Default
- Syntax-highlighted code blocks
- Bordered panels per message
- Spinner/typing indicators during API calls
- Markdown rendering within messages
- Diff highlighting for file changes

**4.3 Input Features**
- Multi-line input support (Shift+Enter or `"""` delimiters)
- Command history (up/down arrows)
- Tab completion for @mentions and commands
- File path autocomplete
- Paste detection for code blocks

**4.4 Status Indicators**
- Model response status (thinking, responding, silent, error)
- Token usage per model (optional, toggle with `/tokens`)
- Active file context display
- Git branch/status in header

---

### 5. Commands

**5.1 Chat Commands**
| Command | Description |
|---------|-------------|
| `@claude`, `@gpt`, `@gemini`, `@grok` | Direct message to specific model |
| `@all` | Force all models to respond |
| `/clear` | Clear conversation (with confirmation) |
| `/pin <message-id>` | Pin message to persistent context |
| `/unpin <message-id>` | Remove pin |
| `/context` | Show current context window status |
| `/retry` | Regenerate last model responses |
| `/solo <model>` | Temporarily chat with only one model |
| `/group` | Return to group mode |

**5.2 File Commands**
| Command | Description |
|---------|-------------|
| `/read <path>` | Read file into context |
| `/write <path>` | Write content to file |
| `/edit <path>` | Interactive file editing |
| `/tree [path]` | Show directory structure |
| `/search <pattern> [path]` | Search in files |
| `/diff <path>` | Show pending changes |

**5.3 Session Commands**
| Command | Description |
|---------|-------------|
| `/save [name]` | Save session with optional name |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a session |
| `/export [format]` | Export conversation (md/json) |

**5.4 System Commands**
| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/config` | Open configuration |
| `/tokens` | Toggle token usage display |
| `/models` | Show model status/availability |
| `/cost` | Show estimated API costs this session |
| `/quit` or `/exit` | Exit CodeCrew |

---

### 6. Configuration

**6.1 Config File Location**
`~/.codecrew/config.yaml`

**6.2 Configuration Options**
```yaml
# API Keys (can also use environment variables)
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
  openai: ${OPENAI_API_KEY}
  google: ${GOOGLE_API_KEY}
  xai: ${XAI_API_KEY}

# Model Settings
models:
  claude:
    enabled: true
    model_id: "claude-sonnet-4-20250514"
    max_tokens: 8192
    temperature: 0.7
  gpt:
    enabled: true
    model_id: "gpt-4o"
    max_tokens: 8192
    temperature: 0.7
  gemini:
    enabled: true
    model_id: "gemini-3-pro"
    max_tokens: 8192
    temperature: 0.7
  grok:
    enabled: true
    model_id: "grok-3"
    max_tokens: 8192
    temperature: 0.7

# Conversation Settings
conversation:
  first_responder: "rotate"  # rotate | claude | gpt | gemini | grok
  silence_threshold: 0.3     # Confidence threshold for "should I speak?"
  max_context_tokens: 100000
  auto_save: true
  save_interval_minutes: 5

# UI Settings
ui:
  theme: "default"           # default | minimal | colorblind
  show_silent_models: true   # Show "X is silent" messages
  show_token_usage: false
  show_cost_estimate: true
  code_theme: "monokai"

# Tool Permissions
tools:
  file_write: true
  file_delete: "confirm"     # true | false | confirm
  shell_execute: "confirm"
  git_operations: true

# Storage
storage:
  database_path: "~/.codecrew/sessions.db"
  max_sessions: 100
```

---

### 7. Tool System

**7.1 Shared Tool Definitions**
All models have access to identical tool definitions for consistency:

```python
TOOLS = {
    "read_file": {
        "description": "Read contents of a file",
        "parameters": {"path": "string"}
    },
    "write_file": {
        "description": "Write content to a file",
        "parameters": {"path": "string", "content": "string"}
    },
    "edit_file": {
        "description": "Make targeted edits to a file",
        "parameters": {"path": "string", "edits": "array"}
    },
    "execute_command": {
        "description": "Run a shell command",
        "parameters": {"command": "string", "cwd": "string?"}
    },
    "search_files": {
        "description": "Search for pattern in files",
        "parameters": {"pattern": "string", "path": "string?"}
    },
    "list_directory": {
        "description": "List files in a directory",
        "parameters": {"path": "string", "recursive": "boolean?"}
    }
}
```

**7.2 Tool Execution**
- Tools are executed by the orchestrator, not models directly
- Results are shared with all models in the conversation
- Confirmation prompts for destructive operations
- Tool calls displayed in UI with collapsible details

**7.3 Model-Specific Adaptations**
- Tool definitions translated to each provider's format
- Claude: Native tool use
- GPT: Function calling
- Gemini: Function declarations
- Grok: Function calling

---

### 8. Architecture

**8.1 High-Level Components**
```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Interface                        │
│                      (rich TUI + input)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Orchestrator                           │
│  - Message routing          - Turn management                │
│  - Context assembly         - "Should speak?" evaluation     │
│  - Tool execution           - Response aggregation           │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Model Client │    │ Model Client │    │ Model Client │  ...
│   (Claude)   │    │    (GPT)     │    │  (Gemini)    │
└──────────────┘    └──────────────┘    └──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Persistence Layer                         │
│           (SQLite: sessions, messages, context)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      File System                             │
│              (Project files, tool operations)                │
└─────────────────────────────────────────────────────────────┘
```

**8.2 Key Classes**
```python
# Core orchestration
class Orchestrator:
    async def process_user_message(message: str) -> list[ModelResponse]
    async def evaluate_should_speak(model: str, context: Context) -> bool
    async def execute_tool(tool_call: ToolCall) -> ToolResult

# Model abstraction
class ModelClient(ABC):
    async def generate(context: Context, tools: list[Tool]) -> Response
    async def should_speak(context: Context) -> tuple[bool, float]

class ClaudeClient(ModelClient): ...
class GPTClient(ModelClient): ...
class GeminiClient(ModelClient): ...
class GrokClient(ModelClient): ...

# Conversation management
class ConversationManager:
    def add_message(role: str, content: str, model: str = None)
    def get_context(model: str, max_tokens: int) -> Context
    def pin_message(message_id: str)
    def save_session() -> str
    def load_session(session_id: str)

# UI
class ChatUI:
    def render_message(message: Message)
    def render_thinking(model: str)
    def render_silent(model: str)
    def get_input() -> str
```

**8.3 Async Flow**
```
User Input
    │
    ▼
Parse for @mentions / commands
    │
    ├─── Command? ──► Execute command, display result
    │
    ▼
Add to conversation history
    │
    ▼
Parallel: Ask each enabled model "should you speak?"
    │
    ▼
Collect models that want to speak (or were @mentioned)
    │
    ▼
Sequential: For each speaking model:
    │   ├─► Generate response (streaming)
    │   ├─► Execute any tool calls
    │   ├─► Add response to history
    │   └─► Render in UI
    │
    ▼
Show silent indicators for non-speaking models
    │
    ▼
Auto-save checkpoint
    │
    ▼
Ready for next input
```

---

### 9. Error Handling

**9.1 API Failures**
- Automatic retry with exponential backoff (3 attempts)
- Graceful degradation: continue conversation without failed model
- Clear error display: "Claude is temporarily unavailable"
- Option to retry failed model: `/retry @claude`

**9.2 Rate Limiting**
- Per-model rate limit tracking
- Queuing when limits approached
- User notification of delays
- Cost-based warnings before expensive operations

**9.3 Context Overflow**
- Automatic summarization of old context
- Warning when approaching limits
- Smart pruning (keep pinned, recent, and high-relevance)

---

### 10. Security Considerations

**10.1 API Key Storage**
- Support environment variables (recommended)
- Encrypted local storage option
- Never log or display API keys
- Warn if keys detected in conversation

**10.2 File System Safety**
- Sandboxed to project directory by default
- Explicit confirmation for operations outside project
- No execution of downloaded code without review
- Audit log of all file operations

**10.3 Command Execution**
- Whitelist of safe commands for auto-execution
- Confirmation required for potentially dangerous commands
- Timeout limits on command execution
- No sudo/admin commands without explicit flag

---

### 11. Future Considerations

**11.1 Potential Enhancements**
- Web UI companion (share sessions, collaborate)
- VS Code / IDE extensions
- Custom model support (local LLMs, other providers)
- Team features (shared sessions, model preferences)
- Plugin system for custom tools
- Voice input/output mode
- Model fine-tuning on user's codebase

**11.2 Analytics (Opt-in)**
- Which models are most helpful for which tasks
- Common conversation patterns
- Tool usage statistics
- Cost optimization recommendations

---

## Technical Requirements

### Dependencies
- Python 3.11+
- `rich` - TUI rendering
- `httpx` / `aiohttp` - Async HTTP
- `anthropic`, `openai`, `google-generativeai` - Official SDKs
- `click` / `typer` - CLI framework
- `sqlite3` - Conversation storage
- `pyyaml` - Configuration
- `prompt_toolkit` - Advanced input handling

### System Requirements
- macOS, Linux, or Windows (WSL recommended)
- Terminal with Unicode and color support
- Internet connection for API calls
- ~50MB disk space for application
- Variable storage for conversation history

---

## Success Metrics

1. **User Engagement:** Average session length > 15 minutes
2. **Multi-Model Value:** >60% of sessions have 2+ models contributing meaningfully
3. **Conversation Resume:** >40% of users resume past sessions
4. **Tool Usage:** >70% of sessions involve file operations
5. **User Retention:** >50% weekly active users return

---

## Launch Plan

**Phase 1: MVP (4 weeks)**
- Core groupchat functionality
- 2 models (Claude + GPT)
- Basic file operations
- Session persistence

**Phase 2: Full Feature (4 weeks)**
- All 4 models
- Complete tool system
- Rich TUI
- Configuration system

**Phase 3: Polish (2 weeks)**
- Performance optimization
- Error handling refinement
- Documentation
- Beta testing

---

## Appendix

### A. Model Personality Guidelines

Each model should maintain its natural personality while being collaborative:

**Claude:** Thoughtful, thorough, acknowledges uncertainty, good at explaining reasoning

**GPT:** Practical, solution-focused, broad knowledge, good at code generation

**Gemini:** Analytical, good at research and documentation, multimodal awareness

**Grok:** Direct, witty, willing to challenge assumptions, real-time knowledge

### B. "Should I Speak?" Prompt Template

```
You are {model_name} in a group coding chat with other AI assistants.

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

Respond with JSON:
{
  "should_speak": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}
```

### C. Sample Conversation Flow

```
You: How should I structure a Next.js app with authentication?

Claude: I'd suggest the App Router with middleware-based auth. Here's
        the structure I'd recommend...
        [provides detailed folder structure and middleware example]

Gemini: Building on Claude's suggestion - if you're using NextAuth.js
        specifically, there's a cleaner pattern with the new v5 beta
        that works better with Server Components...
        [adds NextAuth-specific details]

── GPT is silent ──
── Grok is silent ──

You: @grok what do you think about this approach?

Grok: Claude and Gemini covered the technical side well. My two cents:
      don't over-engineer it. I've seen a lot of Next.js apps turn into
      authentication spaghetti. If you're just doing email/password,
      consider starting with a simpler solution like...

You: Good points. Can someone show me the middleware code?

Claude: Here's a complete middleware.ts example...
        [provides code]

Gemini: One addition to Claude's middleware - you'll want to handle
        the edge case where...
        [adds edge case handling]
```
