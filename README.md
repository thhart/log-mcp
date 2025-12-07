# Log MCP Server

A Model Context Protocol (MCP) server that enables AI assistants to intelligently inspect and analyze runtime log files for debugging and troubleshooting.

## What is this?

This MCP server bridges the gap between your application logs and AI assistants like Claude. When you encounter errors or unexpected behavior in your code, the AI can automatically inspect your runtime logs to diagnose the problem - no more copying and pasting log files back and forth!

**The workflow:**
1. Your applications write logs to a configured directory (e.g., `$XDG_RUNTIME_DIR/log` or custom paths)
2. This MCP server gives your AI assistant read access to those logs
3. When you report a problem, the AI proactively checks the logs to find the root cause
4. Get faster, more accurate debugging assistance based on actual runtime data

## Use Cases

- **Development debugging**: AI analyzes application logs when tests fail or errors occur
- **Service monitoring**: Quickly diagnose issues with background services and daemons
- **Multi-project debugging**: Monitor logs from multiple applications simultaneously
- **Learning & training**: Understand what your code is doing at runtime by having AI explain the logs

## Features

- **Multiple Directory Support**: Monitor logs from multiple directories simultaneously
- **Automatic AI Guidance**: When activated, the AI is informed about log inspection capabilities and will proactively check logs when users report errors
- **list_log_files**: Lists all log files across all configured directories
- **get_log_content**: Reads and returns the content of a specific log file
- **read_log_paginated**: Read large files in chunks with line numbers
- **search_log_file**: Regex search with context lines and pagination
- **runtime-logs prompt**: Provides context to the AI about when and how to use log inspection

## Installation

### From source (development)

```bash
git clone <repository-url>
cd log-mcp
pip install -e .
```

### From PyPI (when published)

```bash
pip install log-inspector-mcp
```

## Usage

### With Claude Desktop

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

**Default directory ($XDG_RUNTIME_DIR/log):**
```json
{
  "mcpServers": {
    "log-inspector": {
      "command": "log-mcp"
    }
  }
}
```

**Single custom directory:**
```json
{
  "mcpServers": {
    "log-inspector": {
      "command": "log-mcp",
      "args": ["--log-dir", "/var/log"]
    }
  }
}
```

**Multiple directories:**
```json
{
  "mcpServers": {
    "log-inspector": {
      "command": "log-mcp",
      "args": [
        "--log-dir", "/var/log",
        "--log-dir", "/tmp/logs",
        "--log-dir", "$XDG_RUNTIME_DIR/log"
      ]
    }
  }
}
```

**Using environment variable (colon-separated):**
```json
{
  "mcpServers": {
    "log-inspector": {
      "command": "log-mcp",
      "env": {
        "LOG_MCP_DIR": "/var/log:/tmp/logs:$XDG_RUNTIME_DIR/log"
      }
    }
  }
}
```

Or using uvx (recommended):

```json
{
  "mcpServers": {
    "log-inspector": {
      "command": "uvx",
      "args": ["log-mcp", "--log-dir", "/var/log"]
    }
  }
}
```

### Standalone

```bash
# Use default directory
log-mcp

# Use single custom directory
log-mcp --log-dir /var/log

# Use multiple directories
log-mcp --log-dir /var/log --log-dir /tmp/logs

# Use environment variable (colon-separated)
LOG_MCP_DIR=/var/log:/tmp/logs log-mcp

# See all options
log-mcp --help
```

### Log Directory Priority

The server determines log directories in this order (highest priority first):
1. `--log-dir` command-line arguments (can be specified multiple times)
2. `LOG_MCP_DIR` environment variable (colon-separated paths, like `PATH`)
3. `$XDG_RUNTIME_DIR/log` (default)

### Multiple Directories

When multiple directories are configured:
- `list_log_files` scans all directories and returns all found files
- Other tools accept either:
  - Just the filename (searches all directories for the file)
  - Full absolute path (must be within one of the allowed directories)

## How It Works

When the MCP server connects to Claude, it automatically informs the AI that:
- Runtime logs are available for inspection
- These logs should be checked whenever users report errors or problems
- The logs contain valuable diagnostic information for troubleshooting

The AI will proactively use the log inspection tools when appropriate.

## Tools

### list_log_files

Lists all log files found in `$XDG_RUNTIME_DIR/log`.

**Parameters**: None

**Returns**: List of full paths to all log files found

**When to use**: First step when investigating any error or problem

### get_log_content

Reads and returns the complete content of a specific log file.

**Parameters**:
- `filename` (string, required): Name of the log file to read

**Returns**: The full content of the specified log file

**When to use**: For small log files; for large files, use read_log_paginated instead

### read_log_paginated

Reads a specific portion of a log file with token-based pagination to respect AI context limits. Tracks file modifications to detect changes during pagination.

**Parameters**:
- `filename` (string, required): Name of the log file to read
- `start_line` (integer, optional): Starting line number (1-based, default: 1)
- `max_tokens` (integer, optional): Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.
- `expected_size` (integer, optional): Expected file size in bytes (from previous call). Warns if file changed.
- `expected_mtime` (number, optional): Expected modification timestamp (from previous call). Warns if file was modified.
- `num_lines` (integer, optional): **DEPRECATED** - Maximum number of lines (max: 1000). If specified, overrides max_tokens for backward compatibility.

**Returns**: Lines with line numbers, file metadata (size, mtime), and warnings if file changed during pagination

**When to use**: For large log files where you need to read specific sections without exceeding context limits

**Examples**:
- Read from start: `start_line=1`
- Read 10000 tokens from line 500: `start_line=500, max_tokens=10000`
- Continue with change detection: `start_line=1234, expected_size=5678910, expected_mtime=1234567890.123`

**File Modification Detection**:
- Each response includes `file_size` and `file_mtime`
- Use these values in the next call as `expected_size` and `expected_mtime`
- If the file changed, you'll get a warning: "⚠️ FILE SIZE CHANGED" or "⚠️ FILE MODIFIED"
- This helps detect when log files are actively being written to

**Why token-based?** Log lines vary drastically in length. Token-based pagination ensures consistent AI context usage regardless of line length.

### search_log_file

Searches a log file using regex patterns and returns matching lines with surrounding context.

**Parameters**:
- `filename` (string, required): Name of the log file to search
- `pattern` (string, required): Regex pattern to search for
- `context_lines` (integer, optional): Lines to show before/after each match (default: 2, max: 10)
- `context_before` (integer, optional): Lines to show before each match (max: 10). Overrides `context_lines` for before-context.
- `context_after` (integer, optional): Lines to show after each match (max: 10). Overrides `context_lines` for after-context.
- `case_sensitive` (boolean, optional): Case-sensitive search (default: false)
- `max_matches` (integer, optional): Maximum matches to return (default: 50, max: 500)
- `skip_matches` (integer, optional): Number of matches to skip for pagination (default: 0)

**Returns**: Matching lines with context, marked with `>>>` for the match line

**When to use**: Searching for specific errors, patterns, or events in log files

**Examples**:
- Search for all "ERROR" entries with 3 lines of context: `context_lines=3`
- Show 5 lines before and 2 after each match: `context_before=5, context_after=2`
- Show only lines after the match: `context_before=0, context_after=5`

## Prompts

### runtime-logs

A prompt that explains to the AI how and when to use log inspection capabilities. This is automatically available when the server connects.

## Example Workflow

1. **Configure your application** to log to `$XDG_RUNTIME_DIR/log/myapp.log`
2. **Add log-mcp to Claude Desktop** config
3. **Run your application** - it writes logs as it runs
4. **Ask Claude for help**: "My application is crashing when I click the submit button"
5. **Claude automatically**:
   - Calls `list_log_files` to see available logs
   - Calls `search_log_file` to find error messages
   - Analyzes the error context
   - Provides a solution based on the actual error

No more manual log copy-pasting! The AI has direct, intelligent access to your runtime diagnostics.

## Configuring Your Applications to Log

For the AI to help debug your applications, they need to write logs to a directory the MCP server monitors. Here are common configuration patterns:

### Default Location: `$XDG_RUNTIME_DIR/log`

On most Linux systems, `$XDG_RUNTIME_DIR` is `/run/user/<UID>` (e.g., `/run/user/1000`). Create the log directory:

```bash
mkdir -p $XDG_RUNTIME_DIR/log
```

### Application-Specific Configuration

#### Node.js / JavaScript

**Using Winston:**
```javascript
const winston = require('winston');

const logger = winston.createLogger({
  transports: [
    new winston.transports.File({
      filename: `${process.env.XDG_RUNTIME_DIR}/log/myapp.log`
    })
  ]
});
```

**Using Pino:**
```javascript
const pino = require('pino');
const logger = pino(
  pino.destination(`${process.env.XDG_RUNTIME_DIR}/log/myapp.log`)
);
```

#### Python

**Using logging module:**
```python
import logging
import os

log_dir = os.path.join(os.environ.get('XDG_RUNTIME_DIR', '/tmp'), 'log')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, 'myapp.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### Java / Spring Boot

**application.properties:**
```properties
logging.file.path=${XDG_RUNTIME_DIR}/log
logging.file.name=${XDG_RUNTIME_DIR}/log/myapp.log
```

#### Rust

**Using `env_logger`:**
```rust
use std::env;
use std::fs::File;

fn setup_logging() {
    let runtime_dir = env::var("XDG_RUNTIME_DIR").unwrap_or("/tmp".to_string());
    let log_file = format!("{}/log/myapp.log", runtime_dir);

    // Configure your logger to write to log_file
}
```

#### Go

```go
package main

import (
    "log"
    "os"
    "path/filepath"
)

func main() {
    runtimeDir := os.Getenv("XDG_RUNTIME_DIR")
    if runtimeDir == "" {
        runtimeDir = "/tmp"
    }

    logPath := filepath.Join(runtimeDir, "log", "myapp.log")
    f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    if err != nil {
        log.Fatal(err)
    }
    log.SetOutput(f)
}
```

### IDE Configuration

#### VSCode (for tasks/debugging)

Create `.vscode/tasks.json`:
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run with logging",
      "type": "shell",
      "command": "node app.js > $XDG_RUNTIME_DIR/log/myapp.log 2>&1"
    }
  ]
}
```

#### IntelliJ IDEA / PyCharm

1. Edit Run Configuration
2. Add VM options or Environment Variables:
   - Set log file path to `$XDG_RUNTIME_DIR/log/myapp.log`
3. Or modify logging configuration file (logback.xml, log4j.properties, etc.)

### Multiple Log Directories

You can monitor logs from different locations simultaneously:

```bash
# System logs + application logs + test logs
log-mcp --log-dir /var/log \
        --log-dir $XDG_RUNTIME_DIR/log \
        --log-dir $HOME/projects/myapp/logs
```

Or use the environment variable:
```bash
export LOG_MCP_DIR="/var/log:$XDG_RUNTIME_DIR/log:$HOME/projects/myapp/logs"
```

## Requirements

- Python 3.10+
- MCP SDK
- `$XDG_RUNTIME_DIR` environment variable (or specify custom directories)
