# Phase 6: Rich TUI Development

## Phase Overview
- **Duration Estimate**: 5 days
- **Dependencies**: Phase 3 (Orchestration Engine), Phase 4 (Conversation Management)
- **Unlocks**: Phase 7 (Commands & User Interaction)
- **Risk Level**: Medium (complex state management, cross-platform rendering)

## Objectives
1. Build a beautiful, responsive terminal UI using Rich library
2. Implement message rendering with model-specific colors and styling
3. Create streaming response display with typing indicators
4. Develop advanced input handling with prompt_toolkit

## Prerequisites
- [ ] Phase 3 completed - orchestrator yields events for UI
- [ ] Phase 4 completed - session info available for display
- [ ] Understanding of Rich library and prompt_toolkit

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| ChatUI class | Code | Main TUI application managing all components |
| Message panels | Code | Styled, bordered panels per model with colors |
| Streaming display | Code | Real-time character rendering during generation |
| Thinking indicators | Code | Spinners/status for each model's state |
| Input handler | Code | Multi-line input, history, tab completion |
| Theme system | Code | Configurable colors including colorblind mode |

## Technical Specifications

### Model Colors
| Model | Color | Hex |
|-------|-------|-----|
| Claude | Orange/Coral | #E07B53 |
| GPT | Green | #10A37F |
| Gemini | Blue | #4285F4 |
| Grok | Purple | #7C3AED |

## Implementation Tasks

### Task Group: Core UI Framework
- [ ] **[TASK-6.1]** Create Theme dataclass and default themes (default, colorblind, minimal)
  - Files: `codecrew/ui/themes.py`
  - Estimate: 1 hour

- [ ] **[TASK-6.2]** Create ChatUI class skeleton with main event loop
  - Files: `codecrew/ui/app.py`
  - Estimate: 2 hours

- [ ] **[TASK-6.3]** Implement header rendering with session info
  - Files: `codecrew/ui/components.py`
  - Estimate: 1.5 hours

### Task Group: Message Rendering
- [ ] **[TASK-6.4]** Implement message panel rendering with model colors
  - Files: `codecrew/ui/components.py`
  - Estimate: 3 hours

- [ ] **[TASK-6.5]** Implement thinking/status indicators with spinners
  - Files: `codecrew/ui/components.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-6.6]** Implement silent model display
  - Files: `codecrew/ui/components.py`
  - Estimate: 0.5 hours

### Task Group: Streaming Display
- [ ] **[TASK-6.7]** Implement streaming response handler with Rich Live
  - Files: `codecrew/ui/streaming.py`
  - Estimate: 3 hours

### Task Group: Input Handling
- [ ] **[TASK-6.8]** Set up prompt_toolkit integration
  - Files: `codecrew/ui/input_handler.py`
  - Estimate: 2 hours

- [ ] **[TASK-6.9]** Implement tab completion for @mentions and commands
  - Files: `codecrew/ui/input_handler.py`
  - Estimate: 2 hours

- [ ] **[TASK-6.10]** Implement multi-line input support
  - Files: `codecrew/ui/input_handler.py`
  - Estimate: 1.5 hours

### Task Group: Event Handling
- [ ] **[TASK-6.11]** Implement event handler for all orchestrator events
  - Files: `codecrew/ui/app.py`
  - Estimate: 2.5 hours

### Task Group: Polish
- [ ] **[TASK-6.12]** Implement tool call display with collapsible details
  - Files: `codecrew/ui/components.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-6.13]** Implement status bar with token usage
  - Files: `codecrew/ui/components.py`
  - Estimate: 1 hour

- [ ] **[TASK-6.14]** Implement diff highlighting for file changes
  - Files: `codecrew/ui/components.py`
  - Estimate: 1 hour

### Task Group: Testing
- [ ] **[TASK-6.15]** Write unit tests for components
  - Files: `tests/test_ui/test_components.py`
  - Estimate: 2 hours

- [ ] **[TASK-6.16]** Write integration test for event handling
  - Files: `tests/test_ui/test_app.py`
  - Estimate: 2 hours

- [ ] **[TASK-6.17]** Manual testing on different terminals
  - Estimate: 2 hours

## Testing Requirements

### Unit Tests
- [ ] Theme loading returns valid Theme objects
- [ ] Message panels render with correct colors
- [ ] Streaming display updates correctly
- [ ] All event types handled without errors

### Manual Verification
- [ ] UI renders correctly on macOS, Linux, Windows Terminal
- [ ] Streaming is smooth
- [ ] Multi-line input works

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All tests passing
- [ ] UI renders correctly cross-platform
- [ ] Code formatted and linted

## Rollback Plan
Fall back to simple print-based UI if Rich causes issues.

## Notes & Considerations
- Test on multiple terminals
- Handle terminals without color support
- Consider small terminal windows
