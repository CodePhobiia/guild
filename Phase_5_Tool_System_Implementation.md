# Phase 5: Tool System Implementation

## Phase Overview
- **Duration Estimate**: 5 days
- **Dependencies**: Phase 3 (Orchestration Engine)
- **Unlocks**: Phase 7 (Commands), Phase 8 (Git Integration)
- **Risk Level**: Medium (file system operations require careful safety)

## Objectives
1. Implement a unified tool registry that manages all available tools
2. Build file system operations (read, write, edit, search, tree)
3. Create shell integration with safety controls
4. Design tool execution framework with confirmations and audit logging

## Prerequisites
- [ ] Phase 3 completed - orchestrator can handle tool calls from models
- [ ] Understanding of file system security considerations
- [ ] Shell execution patterns in Python

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| Tool registry | Code | Register, list, and retrieve tool definitions |
| Tool executor | Code | Execute tools with permission checks |
| File operations | Code | read_file, write_file, edit_file, search_files, list_directory |
| Shell integration | Code | execute_command with safety controls |
| Confirmation system | Code | Interactive prompts for destructive operations |
| Audit logger | Code | Log all file and shell operations |

## Technical Specifications

### Architecture Decisions
1. **Central Tool Registry**: Single source of truth for all tool definitions
2. **Executor Pattern**: Separate tool definition from execution logic
3. **Permission-Based Execution**: Config-driven permissions (allow, deny, confirm)
4. **Sandboxed by Default**: File operations restricted to project directory
5. **Audit Trail**: All operations logged for review
6. **Unified Results**: Tools return consistent result format

### Component Breakdown

#### Tool Registry (`codecrew/tools/registry.py`)
- **Purpose**: Central registration and retrieval of all tools
- **Location**: `codecrew/tools/registry.py`

#### Tool Executor (`codecrew/tools/executor.py`)
- **Purpose**: Execute tools with permission checks and logging
- **Location**: `codecrew/tools/executor.py`

#### File Operations (`codecrew/tools/file_ops.py`)
- **Purpose**: All file system operations
- **Location**: `codecrew/tools/file_ops.py`

#### Shell Integration (`codecrew/tools/shell.py`)
- **Purpose**: Execute shell commands safely
- **Location**: `codecrew/tools/shell.py`

## Implementation Tasks

### Task Group: Tool Infrastructure
- [ ] **[TASK-5.1]** Create Tool and ToolResult dataclasses
  - Files: `codecrew/tools/types.py`
  - Estimate: 1 hour

- [ ] **[TASK-5.2]** Implement ToolRegistry
  - Files: `codecrew/tools/registry.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-5.3]** Implement ToolExecutor with permission checks
  - Files: `codecrew/tools/executor.py`
  - Estimate: 2.5 hours

- [ ] **[TASK-5.4]** Implement path validation and sandboxing
  - Files: `codecrew/tools/security.py`
  - Estimate: 1.5 hours

### Task Group: File Operations
- [ ] **[TASK-5.5]** Implement read_file tool
  - Files: `codecrew/tools/file_ops.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-5.6]** Implement write_file tool
  - Files: `codecrew/tools/file_ops.py`
  - Estimate: 2 hours

- [ ] **[TASK-5.7]** Implement edit_file tool with diff support
  - Files: `codecrew/tools/file_ops.py`
  - Estimate: 2.5 hours

- [ ] **[TASK-5.8]** Implement search_files tool
  - Files: `codecrew/tools/file_ops.py`
  - Estimate: 2 hours

- [ ] **[TASK-5.9]** Implement list_directory tool (tree view)
  - Files: `codecrew/tools/file_ops.py`
  - Estimate: 2 hours

### Task Group: Shell Integration
- [ ] **[TASK-5.10]** Implement execute_command tool
  - Files: `codecrew/tools/shell.py`
  - Estimate: 3 hours

- [ ] **[TASK-5.11]** Implement streaming output for long-running commands
  - Files: `codecrew/tools/shell.py`
  - Estimate: 1.5 hours

### Task Group: Utility and Support
- [ ] **[TASK-5.12]** Implement diff generation
  - Files: `codecrew/tools/diff.py`
  - Estimate: 1 hour

- [ ] **[TASK-5.13]** Implement backup system
  - Files: `codecrew/tools/backup.py`
  - Estimate: 1 hour

- [ ] **[TASK-5.14]** Implement AuditLogger
  - Files: `codecrew/tools/audit.py`
  - Estimate: 1 hour

### Task Group: Registration and Integration
- [ ] **[TASK-5.15]** Register all tools on module import
  - Files: `codecrew/tools/__init__.py`
  - Estimate: 0.5 hours

- [ ] **[TASK-5.16]** Integrate ToolExecutor with Orchestrator
  - Files: `codecrew/orchestrator/engine.py`
  - Estimate: 1.5 hours

### Task Group: Testing
- [ ] **[TASK-5.17]** Write unit tests for file operations
  - Files: `tests/test_tools/test_file_ops.py`
  - Estimate: 2.5 hours

- [ ] **[TASK-5.18]** Write unit tests for shell integration
  - Files: `tests/test_tools/test_shell.py`
  - Estimate: 2 hours

- [ ] **[TASK-5.19]** Write unit tests for path validation
  - Files: `tests/test_tools/test_security.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-5.20]** Write integration tests for tool execution flow
  - Files: `tests/test_tools/test_executor.py`
  - Estimate: 2 hours

## Testing Requirements

### Unit Tests
- [ ] File operations handle all edge cases (binary, missing, permissions)
- [ ] Edit tool generates accurate diffs
- [ ] Search respects patterns and limits results
- [ ] Shell commands respect timeout and blocked patterns
- [ ] Path validator catches sandbox escapes

### Integration Tests
- [ ] Tool registry returns all registered tools
- [ ] Executor calls confirmation for flagged tools
- [ ] Tools integrate with orchestrator events

### Manual Verification
- [ ] All file operations work correctly
- [ ] Shell commands execute safely
- [ ] Audit log captures operations

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All tests passing
- [ ] Security measures verified
- [ ] Code formatted and linted

## Rollback Plan
Disable individual tools via config if issues arise. Fall back to read-only operations.

## Notes & Considerations
- Always validate paths before operations
- Create backups before modifications
- Log all destructive operations
- Block known dangerous command patterns
