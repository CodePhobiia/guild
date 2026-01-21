# Phase 7: Commands & User Interaction

## Phase Overview
- **Duration Estimate**: 3 days
- **Dependencies**: Phase 5 (Tool System), Phase 6 (TUI)
- **Unlocks**: Phase 8 (Git Integration)
- **Risk Level**: Low

## Objectives
1. Implement all slash commands from the PRD
2. Build command parser with argument handling
3. Create confirmation dialogs for destructive operations
4. Implement /solo and /group mode switching

## Prerequisites
- [ ] Phase 5 completed - tools available for /read, /write, etc.
- [ ] Phase 6 completed - UI can render command outputs

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| Command parser | Code | Parse /commands with arguments |
| Chat commands | Code | /clear, /pin, /unpin, /context, /retry, /solo, /group |
| File commands | Code | /read, /write, /edit, /tree, /search, /diff |
| Session commands | Code | /save, /sessions, /resume, /export |
| System commands | Code | /help, /config, /tokens, /models, /cost, /quit |

## Technical Specifications

### Command Structure
```python
@dataclass
class ParsedCommand:
    name: str
    args: List[str]
    kwargs: Dict[str, str]
    raw: str

class CommandHandler(ABC):
    name: str
    aliases: List[str]
    description: str
    usage: str
    
    @abstractmethod
    async def execute(
        self,
        args: List[str],
        context: CommandContext,
    ) -> CommandResult: ...
```

## Implementation Tasks

### Task Group: Command Infrastructure
- [ ] **[TASK-7.1]** Implement command parser
  - Files: `codecrew/commands/parser.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-7.2]** Create CommandHandler base class
  - Files: `codecrew/commands/base.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.3]** Implement command registry
  - Files: `codecrew/commands/__init__.py`
  - Estimate: 1 hour

### Task Group: Chat Commands
- [ ] **[TASK-7.4]** Implement /help command
  - Files: `codecrew/commands/system.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.5]** Implement /clear command with confirmation
  - Files: `codecrew/commands/chat.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.6]** Implement /pin and /unpin commands
  - Files: `codecrew/commands/chat.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.7]** Implement /context command
  - Files: `codecrew/commands/chat.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.8]** Implement /retry command
  - Files: `codecrew/commands/chat.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.9]** Implement /solo and /group commands
  - Files: `codecrew/commands/chat.py`
  - Estimate: 1.5 hours

### Task Group: File Commands
- [ ] **[TASK-7.10]** Implement /read command
  - Files: `codecrew/commands/file.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.11]** Implement /write command
  - Files: `codecrew/commands/file.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.12]** Implement /edit command
  - Files: `codecrew/commands/file.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.13]** Implement /tree command
  - Files: `codecrew/commands/file.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.14]** Implement /search command
  - Files: `codecrew/commands/file.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.15]** Implement /diff command
  - Files: `codecrew/commands/file.py`
  - Estimate: 0.5 hours

### Task Group: Session Commands
- [ ] **[TASK-7.16]** Implement /save command
  - Files: `codecrew/commands/session.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.17]** Implement /sessions command
  - Files: `codecrew/commands/session.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.18]** Implement /resume command
  - Files: `codecrew/commands/session.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.19]** Implement /export command
  - Files: `codecrew/commands/session.py`
  - Estimate: 1 hour

### Task Group: System Commands
- [ ] **[TASK-7.20]** Implement /config command
  - Files: `codecrew/commands/system.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.21]** Implement /tokens command
  - Files: `codecrew/commands/system.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.22]** Implement /models command
  - Files: `codecrew/commands/system.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.23]** Implement /cost command
  - Files: `codecrew/commands/system.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-7.24]** Implement /quit and /exit commands
  - Files: `codecrew/commands/system.py`
  - Estimate: 0.5 hours

### Task Group: Testing
- [ ] **[TASK-7.25]** Write unit tests for command parser
  - Files: `tests/test_commands/test_parser.py`
  - Estimate: 1 hour

- [ ] **[TASK-7.26]** Write tests for all command handlers
  - Files: `tests/test_commands/test_*.py`
  - Estimate: 2 hours

## Testing Requirements

### Unit Tests
- [ ] Parser extracts command name and arguments correctly
- [ ] All commands execute without errors
- [ ] /help displays all available commands
- [ ] /solo switches to single-model mode
- [ ] /group returns to group mode

### Manual Verification
- [ ] All commands work as documented
- [ ] Tab completion includes all commands
- [ ] Error messages are helpful

## Phase Completion Checklist
- [ ] All commands implemented and tested
- [ ] Tab completion updated with all commands
- [ ] Help text accurate for all commands

## Rollback Plan
Commands are independent - disable individual commands if issues arise.

## Notes & Considerations
- Commands should be discoverable via /help
- Provide helpful error messages for invalid usage
