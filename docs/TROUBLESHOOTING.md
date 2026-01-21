# Troubleshooting Guide

This guide helps you resolve common issues with CodeCrew.

## Table of Contents

- [Installation Issues](#installation-issues)
- [API Key Problems](#api-key-problems)
- [Connection Errors](#connection-errors)
- [Tool Execution Issues](#tool-execution-issues)
- [UI and Display Problems](#ui-and-display-problems)
- [Performance Issues](#performance-issues)
- [Database Issues](#database-issues)

## Installation Issues

### Python Version Error

**Error:**
```
ERROR: This package requires Python >=3.11
```

**Solution:**
Install Python 3.11 or higher:
```bash
# Check your Python version
python --version

# Install Python 3.11+ from python.org or use pyenv
pyenv install 3.11.5
pyenv local 3.11.5
```

### Package Not Found

**Error:**
```
ModuleNotFoundError: No module named 'codecrew'
```

**Solution:**
```bash
# Ensure codecrew is installed
pip install codecrew

# Or install in development mode
pip install -e .
```

### Dependency Conflicts

**Error:**
```
ERROR: Cannot install codecrew because these package versions have conflicting dependencies
```

**Solution:**
```bash
# Create a fresh virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install codecrew
```

## API Key Problems

### Key Not Configured

**Error:**
```
AuthenticationError: API key not configured for claude
```

**Solution:**

1. Set environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

2. Or add to config file `~/.codecrew/config.yaml`:
```yaml
api_keys:
  anthropic: sk-ant-...
```

### Invalid API Key

**Error:**
```
AuthenticationError: Invalid API key
```

**Solution:**
1. Verify your API key is correct
2. Check that the key hasn't expired
3. Ensure you have an active subscription with the provider

### Rate Limit Exceeded

**Error:**
```
RateLimitError: Rate limit exceeded
```

**Solution:**
1. Wait a few minutes before retrying
2. Reduce the frequency of requests
3. Consider upgrading your API plan
4. CodeCrew automatically retries with exponential backoff

## Connection Errors

### Timeout

**Error:**
```
APIError: Connection timed out
```

**Solution:**
1. Check your internet connection
2. Verify the API service is operational
3. Try again later
4. Check firewall settings

### SSL Certificate Error

**Error:**
```
SSLError: Certificate verify failed
```

**Solution:**
```bash
# Update certificates
pip install --upgrade certifi

# Or on macOS
/Applications/Python\ 3.11/Install\ Certificates.command
```

### Proxy Issues

**Error:**
```
ProxyError: Unable to connect through proxy
```

**Solution:**
Set proxy environment variables:
```bash
export HTTP_PROXY="http://proxy:port"
export HTTPS_PROXY="http://proxy:port"
```

## Tool Execution Issues

### Permission Denied

**Error:**
```
PathAccessError: Path is outside allowed directories
```

**Solution:**
Add the path to `allowed_paths` in your config:
```yaml
tools:
  allowed_paths:
    - ./
    - ~/projects
    - /path/to/your/code
```

### Command Blocked

**Error:**
```
CommandBlockedError: Command is blocked for security
```

**Solution:**
The command was blocked for safety. If you need to run it:
1. Run the command manually in your terminal
2. Or reconsider if the command is safe

### Tool Timeout

**Error:**
```
ToolError: Tool execution timed out
```

**Solution:**
Increase the timeout in config:
```yaml
tools:
  tool_timeout: 60  # seconds
```

### File Not Found

**Error:**
```
Tool Error: File not found: /path/to/file
```

**Solution:**
1. Verify the file path is correct
2. Use absolute paths or paths relative to working directory
3. Check file permissions

## UI and Display Problems

### Unicode Characters Not Displaying

**Symptom:** Boxes or question marks instead of symbols

**Solution:**
1. Use a terminal with Unicode support
2. Or disable Unicode in config:
```yaml
ui:
  use_unicode: false
```

### Colors Not Working

**Symptom:** No colors or garbled output

**Solution:**
1. Enable true color in your terminal
2. Try a different theme:
```yaml
ui:
  theme: high_contrast
```

### Screen Flickering

**Symptom:** Display flickers during updates

**Solution:**
1. Update your terminal emulator
2. Try enabling compact mode:
```yaml
ui:
  compact_mode: true
```

### Input Not Working

**Symptom:** Cannot type or cursor not visible

**Solution:**
1. Press `Ctrl+L` to refresh the display
2. Restart CodeCrew
3. Try a different terminal emulator

## Performance Issues

### High Memory Usage

**Symptom:** CodeCrew using excessive memory

**Solution:**
1. Reduce context window:
```yaml
conversation:
  max_context_tokens: 50000
```

2. Enable summarization:
```yaml
conversation:
  enable_summarization: true
  summarization_threshold: 30000
```

3. Clear conversation history:
```
/clear
```

### Slow Responses

**Symptom:** Long wait times for AI responses

**Solution:**
1. Check your internet connection
2. Use a faster model:
```yaml
models:
  claude:
    model_id: claude-3-haiku-20240307
```

3. Reduce max_tokens:
```yaml
models:
  claude:
    max_tokens: 4096
```

### High Token Usage

**Symptom:** Consuming too many tokens

**Solution:**
1. Use `/clear` to reset context
2. Be more concise in prompts
3. Reduce context window in config

## Database Issues

### Database Locked

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
1. Close any other CodeCrew instances
2. Wait and retry
3. Delete the lock file:
```bash
rm ~/.codecrew/conversations.db-wal
rm ~/.codecrew/conversations.db-shm
```

### Corrupted Database

**Error:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**Solution:**
1. Back up your database
2. Try to recover:
```bash
sqlite3 ~/.codecrew/conversations.db ".recover" | sqlite3 recovered.db
mv recovered.db ~/.codecrew/conversations.db
```

3. Or start fresh:
```bash
rm ~/.codecrew/conversations.db
```

### Migration Failed

**Error:**
```
Migration Error: Failed to apply migration
```

**Solution:**
1. Back up your database
2. Try running with a fresh database
3. Report the issue on GitHub with your database version

## Getting More Help

### Enable Debug Logging

```yaml
logging:
  level: debug
  file: ~/.codecrew/debug.log
```

### Check Logs

```bash
# View recent logs
tail -100 ~/.codecrew/codecrew.log

# Search for errors
grep -i error ~/.codecrew/codecrew.log
```

### Report Issues

If you can't resolve the issue:

1. Search [existing issues](https://github.com/CodePhobiia/guild/issues)
2. Create a new issue with:
   - CodeCrew version (`codecrew --version`)
   - Python version (`python --version`)
   - Operating system
   - Full error message
   - Steps to reproduce
   - Relevant configuration (remove API keys!)

### Community Support

- GitHub Issues: https://github.com/CodePhobiia/guild/issues
- Discussions: https://github.com/CodePhobiia/guild/discussions
