# Phase 8: Git Integration & Project Intelligence

## Phase Overview
- **Duration Estimate**: 3 days
- **Dependencies**: Phase 5 (Tool System)
- **Unlocks**: Phase 9 (Polish & Security)
- **Risk Level**: Low

## Objectives
1. Implement Git operations (status, diff, log, commit, branch)
2. Build project type detection (Node.js, Python, Go, etc.)
3. Create framework-specific knowledge integration
4. Implement dependency graph awareness

## Prerequisites
- [ ] Phase 5 completed - tool system for executing git commands
- [ ] Git installed on system
- [ ] Understanding of common project structures

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| Git tools | Code | status, diff, log, commit, branch operations |
| Project detector | Code | Detects project type from files/config |
| Framework knowledge | Code | Context-aware suggestions per framework |
| Dependency parser | Code | Parse package.json, requirements.txt, etc. |

## Technical Specifications

### Git Operations
```python
# Safe git commands (no confirmation needed)
SAFE_GIT = {"status", "diff", "log", "branch", "show", "blame"}

# Commands requiring confirmation
CONFIRM_GIT = {"commit", "push", "merge", "rebase", "reset"}

# Blocked commands
BLOCKED_GIT = {"push --force", "reset --hard", "clean -fd"}
```

### Project Types
| Type | Detection Files |
|------|-----------------|
| Node.js | package.json |
| Python | pyproject.toml, setup.py, requirements.txt |
| Go | go.mod |
| Rust | Cargo.toml |
| Ruby | Gemfile |
| Java | pom.xml, build.gradle |

## Implementation Tasks

### Task Group: Git Tools
- [ ] **[TASK-8.1]** Implement git status tool
  - Files: `codecrew/tools/git.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.2]** Implement git diff tool
  - Files: `codecrew/tools/git.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.3]** Implement git log tool with formatting
  - Files: `codecrew/tools/git.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.4]** Implement git commit with message generation
  - Files: `codecrew/tools/git.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-8.5]** Implement git branch operations
  - Files: `codecrew/tools/git.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.6]** Register git tools in registry
  - Files: `codecrew/tools/__init__.py`
  - Estimate: 0.5 hours

### Task Group: Project Detection
- [ ] **[TASK-8.7]** Create ProjectDetector class
  - Files: `codecrew/project/detector.py`
  - Estimate: 2 hours

- [ ] **[TASK-8.8]** Implement detection rules for common project types
  - Files: `codecrew/project/detector.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-8.9]** Parse and expose project metadata
  - Files: `codecrew/project/metadata.py`
  - Estimate: 1.5 hours

### Task Group: Framework Knowledge
- [ ] **[TASK-8.10]** Create framework context providers
  - Files: `codecrew/project/frameworks.py`
  - Estimate: 2 hours

- [ ] **[TASK-8.11]** Integrate project context into model prompts
  - Files: `codecrew/orchestrator/context.py`
  - Estimate: 1 hour

### Task Group: Dependency Awareness
- [ ] **[TASK-8.12]** Implement package.json parser
  - Files: `codecrew/project/parsers/npm.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.13]** Implement requirements.txt/pyproject.toml parser
  - Files: `codecrew/project/parsers/python.py`
  - Estimate: 1 hour

- [ ] **[TASK-8.14]** Create unified dependency interface
  - Files: `codecrew/project/dependencies.py`
  - Estimate: 1 hour

### Task Group: Testing
- [ ] **[TASK-8.15]** Write tests for git tools
  - Files: `tests/test_tools/test_git.py`
  - Estimate: 1.5 hours

- [ ] **[TASK-8.16]** Write tests for project detection
  - Files: `tests/test_project/test_detector.py`
  - Estimate: 1.5 hours

## Testing Requirements

### Unit Tests
- [ ] Git status parses clean/dirty states
- [ ] Git diff shows file changes
- [ ] Project detector identifies correct types
- [ ] Dependency parsers extract packages

### Manual Verification
- [ ] Git operations work in real repo
- [ ] Project detection works on various project types
- [ ] Git branch shown in UI header

## Phase Completion Checklist
- [ ] All git operations working
- [ ] Project detection accurate
- [ ] Framework context integrated
- [ ] Tests passing

## Rollback Plan
Git and project features are additive - disable if issues arise without affecting core functionality.

## Notes & Considerations
- Handle repos with uncommitted changes carefully
- Respect .gitignore for file operations
- Don't expose sensitive data from git history
