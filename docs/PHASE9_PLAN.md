# Phase 9: Polish, Security, Error Handling

## Overview

Phase 9 focuses on hardening CodeCrew for production use by addressing security vulnerabilities, improving error handling consistency, adding input validation, and polishing the codebase.

## Priority Areas

### P0 - Security Vulnerabilities (Critical)

1. **Shell Injection Prevention** (`codecrew/tools/builtin/shell.py`)
   - Current: Uses `shell=True` which is vulnerable to injection
   - Fix: Use `shlex.split()` and `shell=False` where possible
   - Add stricter command validation and escaping
   - Implement allowlist for safe shell features

2. **Path Traversal Protection** (`codecrew/tools/builtin/files.py`)
   - Current: `startswith()` check is insufficient
   - Fix: Use `Path.is_relative_to()` for proper containment check
   - Validate symlink resolution doesn't escape allowed paths
   - Add explicit blocklist for sensitive paths

3. **Git Path Validation** (`codecrew/tools/builtin/git.py`)
   - Add working directory validation
   - Ensure git operations stay within project bounds

### P1 - Error Handling (High)

1. **Custom Exception Hierarchy** (`codecrew/errors.py` - new file)
   ```
   CodeCrewError (base)
   ├── ConfigurationError
   ├── ModelError
   │   ├── APIError
   │   ├── RateLimitError
   │   └── AuthenticationError
   ├── ToolError
   │   ├── ToolExecutionError (exists)
   │   ├── ToolValidationError
   │   └── PermissionDeniedError
   ├── ConversationError
   │   ├── SessionNotFoundError
   │   └── PersistenceError
   ├── GitError (exists in git/utils.py)
   └── UIError
   ```

2. **Replace Bare Exceptions**
   - `codecrew/cli.py`: 4 locations
   - `codecrew/ui/app.py`: 5 locations
   - `codecrew/models/*.py`: 10+ locations
   - `codecrew/tools/executor.py`: 1 location
   - `codecrew/ui/handlers/commands.py`: 6 locations

3. **Add Error Recovery**
   - Implement retry logic for transient failures
   - Add graceful degradation for non-critical errors
   - Ensure database operations have proper rollback

### P2 - Input Validation (Medium)

1. **Parameter Validation**
   - Add bounds checking for `limit` parameters
   - Validate session/message IDs format
   - Check string lengths before processing
   - Validate JSON schema for tool arguments

2. **SQL Injection Prevention**
   - Review all SQL queries for proper parameterization
   - Add input sanitization for LIKE queries

3. **API Input Validation**
   - Validate API keys format before use
   - Check model IDs against supported list
   - Validate message content length

### P3 - Logging Improvements (Medium)

1. **Consistent Log Levels**
   - DEBUG: Internal operations, verbose output
   - INFO: User-visible operations, state changes
   - WARNING: Recoverable issues, deprecations
   - ERROR: Failures requiring attention

2. **Security-Sensitive Logging**
   - Redact API keys in all logs
   - Don't log full file contents
   - Mask command outputs in debug logs

3. **Add Missing Logging**
   - Speaker decisions in orchestrator
   - Permission checks in executor
   - Pin/unpin operations

### P4 - Code Polish (Low)

1. **Type Hints**
   - Add missing return type annotations
   - Replace `Any` with specific types
   - Add TypedDict for complex dictionaries

2. **Docstrings**
   - Document all public functions
   - Add parameter descriptions
   - Include usage examples

3. **Consistency**
   - Standardize timeout handling
   - Unify file encoding patterns
   - Consistent async/sync boundaries

## Implementation Plan

### Step 1: Security Hardening (shell.py, files.py, git.py)
- Implement secure command execution
- Add path containment validation
- Add security tests

### Step 2: Exception Hierarchy (errors.py)
- Create centralized exception module
- Define exception hierarchy
- Add error codes and messages

### Step 3: Error Handling Refactor
- Replace bare exceptions with specific types
- Add error context and recovery
- Update tests

### Step 4: Input Validation
- Add validation utilities
- Implement validators across modules
- Add validation tests

### Step 5: Logging Enhancement
- Standardize log levels
- Add security redaction
- Fill logging gaps

### Step 6: Final Polish
- Type hints completion
- Docstring review
- Code consistency pass

## Files to Create/Modify

### New Files
- `codecrew/errors.py` - Exception hierarchy
- `codecrew/validation.py` - Input validation utilities
- `codecrew/security.py` - Security utilities
- `tests/test_security.py` - Security tests
- `tests/test_validation.py` - Validation tests

### Modified Files
- `codecrew/tools/builtin/shell.py` - Security hardening
- `codecrew/tools/builtin/files.py` - Path validation
- `codecrew/tools/builtin/git.py` - Path validation
- `codecrew/cli.py` - Error handling
- `codecrew/ui/app.py` - Error handling
- `codecrew/models/*.py` - Error handling
- `codecrew/tools/executor.py` - Error handling
- `codecrew/conversation/persistence.py` - Validation, error handling
- All modules - Logging consistency

## Success Criteria

1. **Security**
   - No shell injection vulnerabilities
   - No path traversal vulnerabilities
   - All user inputs validated

2. **Error Handling**
   - No bare `except Exception` blocks
   - All errors have meaningful messages
   - Graceful degradation for non-critical failures

3. **Validation**
   - All public APIs validate inputs
   - SQL queries properly parameterized
   - Bounds checks on all limits

4. **Logging**
   - Consistent log levels across modules
   - No sensitive data in logs
   - Sufficient debug context

5. **Tests**
   - Security vulnerability tests
   - Error handling tests
   - Input validation tests
