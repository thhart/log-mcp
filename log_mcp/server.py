"""MCP server for inspecting log files in XDG_RUNTIME_DIR/log."""

import os
import re
import sys
import argparse
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, Prompt, PromptMessage, GetPromptResult
import mcp.server.stdio

# Global variable to store the log directory paths
LOG_DIRECTORIES = []

app = Server("log-inspector")


def get_log_directories() -> list[Path]:
    """Get the log directory paths based on priority: CLI args > env var > default."""
    global LOG_DIRECTORIES

    if LOG_DIRECTORIES:
        return [Path(d) for d in LOG_DIRECTORIES]

    # Check environment variable (colon-separated like PATH)
    if env_dirs := os.getenv("LOG_MCP_DIR"):
        return [Path(d.strip()) for d in env_dirs.split(":") if d.strip()]

    # Default to XDG_RUNTIME_DIR/log
    xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    if not xdg_runtime_dir:
        raise ValueError("XDG_RUNTIME_DIR not set and no log directory specified")

    return [Path(xdg_runtime_dir) / "log"]


def resolve_log_file(filename: str) -> tuple[Path, Path]:
    """
    Resolve a filename to a full path within allowed directories.

    Returns: (log_dir, log_file) tuple
    Raises: ValueError if file is not found or not in allowed directories
    """
    directories = get_log_directories()

    # If filename is already an absolute path, validate it's in allowed dirs
    file_path = Path(filename)
    if file_path.is_absolute():
        try:
            resolved = file_path.resolve()
            for log_dir in directories:
                if str(resolved).startswith(str(log_dir.resolve())):
                    return log_dir, resolved
        except Exception:
            pass
        raise ValueError(f"File not in any allowed log directory: {filename}")

    # Try to find the file in each directory
    for log_dir in directories:
        log_file = log_dir / filename
        if log_file.exists():
            return log_dir, log_file.resolve()

    # If not found, use the first directory (for error messages)
    if directories:
        return directories[0], (directories[0] / filename).resolve()

    raise ValueError("No log directories configured")


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    return [
        Prompt(
            name="runtime-logs",
            description="Information about runtime log inspection capabilities",
        )
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    """Get prompt content."""
    if name == "runtime-logs":
        try:
            log_dirs = get_log_directories()
            log_dirs_str = "\n".join(f"  - {d}" for d in log_dirs)
        except ValueError:
            log_dirs_str = "  - /run/user/[UID]/log"

        message = f"""# Runtime Log Inspection Available

This MCP server provides access to runtime logs stored in:
{log_dirs_str}

## Important: When to Use Log Inspection

**ALWAYS check runtime logs when:**
- The user reports errors or problems with their code
- There are runtime failures, crashes, or unexpected behavior
- The user mentions something "not working" or "failing"
- Debugging is needed for any application or service
- You need to understand what happened during execution

## Available Tools

1. **list_log_files** - Lists all available log files in the runtime directory
2. **get_log_content** - Reads the content of a specific log file (for small files)
3. **read_log_paginated** - Reads a portion of a log file with pagination (for large files)
4. **search_log_file** - Searches log files with regex and shows matching lines with context

## Recommended Workflow

When a user reports a problem:
1. First use `list_log_files` to see what logs are available
2. Then use `get_log_content` to inspect relevant log files
3. Analyze the logs to identify the root cause
4. Provide solutions based on the actual error messages found

These logs contain real-time diagnostic information that is invaluable for troubleshooting."""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=message
                    )
                )
            ]
        )
    else:
        raise ValueError(f"Unknown prompt: {name}")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_log_files",
            description="Lists all log files in $XDG_RUNTIME_DIR/log. Use this FIRST when user reports errors or problems to see what logs are available for inspection.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_log_content",
            description="Returns the content of a specific log file from $XDG_RUNTIME_DIR/log. Use this to inspect runtime logs when debugging errors or investigating problems. For large files, use read_log_paginated instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to read"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="read_log_paginated",
            description="Reads a paginated portion of a log file. Useful for large log files. Uses token-based pagination to respect AI context limits. Tracks file modifications to detect changes between pagination calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to read"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-based, default: 1)",
                        "default": 1
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    },
                    "num_lines": {
                        "type": "integer",
                        "description": "DEPRECATED: Use max_tokens instead. Maximum number of lines (max: 1000). If specified, overrides max_tokens."
                    },
                    "expected_size": {
                        "type": "integer",
                        "description": "Expected file size in bytes (from previous call). If file size changed, returns a warning."
                    },
                    "expected_mtime": {
                        "type": "number",
                        "description": "Expected modification time timestamp (from previous call). If file was modified, returns a warning."
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="search_log_file",
            description="Searches a log file using regex pattern and returns matching lines with surrounding context. Supports token-based pagination to respect AI context limits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to search"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each match (default: 2, max: 10). Overridden by context_before/context_after if specified.",
                        "default": 2
                    },
                    "context_before": {
                        "type": "integer",
                        "description": "Number of lines to show before each match (max: 10). Overrides context_lines for before-context."
                    },
                    "context_after": {
                        "type": "integer",
                        "description": "Number of lines to show after each match (max: 10). Overrides context_lines for after-context."
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: false)",
                        "default": False
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation. When specified, overrides max_matches.",
                        "default": 4000
                    },
                    "max_matches": {
                        "type": "integer",
                        "description": "DEPRECATED: Use max_tokens instead. Maximum number of matches to return (max: 500). If specified, overrides max_tokens."
                    },
                    "skip_matches": {
                        "type": "integer",
                        "description": "Number of matches to skip (for pagination, default: 0)",
                        "default": 0
                    }
                },
                "required": ["filename", "pattern"]
            }
        ),
        Tool(
            name="head_log",
            description="Reads the beginning of a log file (like Unix 'head' command). Uses token-based pagination to respect AI context limits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to read"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to read from the beginning. If not specified, uses token-based limit."
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="tail_log",
            description="Reads the end of a log file (like Unix 'tail' command). Uses token-based pagination to respect AI context limits. Ideal for checking recent log entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to read"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to read from the end. If not specified, uses token-based limit."
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="read_log_range",
            description="Reads a specific range of lines from a log file. Uses token-based pagination to respect AI context limits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to read"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-based, inclusive)",
                        "default": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-based, inclusive). If not specified, reads to end of file or token limit."
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="find_errors",
            description="Quickly finds error lines in a log file by matching common error patterns (ERROR, Exception, FATAL, Failed, Traceback, panic, etc.). Ideal for quick diagnostics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the log file to search"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each error (default: 2, max: 10)",
                        "default": 2
                    },
                    "include_warnings": {
                        "type": "boolean",
                        "description": "Also include warning-level messages (default: false)",
                        "default": False
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to return (default: 4000, max: 100000). Uses ~4 chars per token estimation.",
                        "default": 4000
                    }
                },
                "required": ["filename"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "list_log_files":
        try:
            log_dirs = get_log_directories()
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        all_log_files = []
        errors = []

        # Scan all log directories
        for log_dir in log_dirs:
            if not log_dir.exists():
                errors.append(f"Directory does not exist: {log_dir}")
                continue

            if not log_dir.is_dir():
                errors.append(f"Path exists but is not a directory: {log_dir}")
                continue

            try:
                for item in log_dir.iterdir():
                    if item.is_file():
                        all_log_files.append(str(item.absolute()))
            except PermissionError:
                errors.append(f"Permission denied accessing: {log_dir}")

        if not all_log_files and not errors:
            return [TextContent(
                type="text",
                text=f"No log files found in any directory"
            )]

        result = f"Scanning {len(log_dirs)} log director{'y' if len(log_dirs) == 1 else 'ies'}:\n"
        result += "\n".join(f"  - {d}" for d in log_dirs)
        result += f"\n\nFound {len(all_log_files)} log file(s):\n\n"
        result += "\n".join(sorted(all_log_files))

        if errors:
            result += "\n\nWarnings:\n" + "\n".join(f"  - {e}" for e in errors)

        return [TextContent(type="text", text=result)]

    elif name == "get_log_content":
        filename = arguments.get("filename")
        max_tokens = min(arguments.get("max_tokens", 4000), 100000)

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        try:
            content = log_file.read_text()
            file_size = log_file.stat().st_size
            total_tokens = len(content) // 4

            if total_tokens <= max_tokens:
                return [TextContent(
                    type="text",
                    text=f"Content of {log_file} ({file_size} bytes, ~{total_tokens} tokens):\n\n{content}"
                )]
            else:
                # Truncate to max_tokens
                max_chars = max_tokens * 4
                truncated_content = content[:max_chars]
                # Try to break at a newline for cleaner output
                last_newline = truncated_content.rfind('\n')
                if last_newline > max_chars * 0.8:  # Only break at newline if we keep >80% of content
                    truncated_content = truncated_content[:last_newline]

                actual_tokens = len(truncated_content) // 4
                return [TextContent(
                    type="text",
                    text=f"Content of {log_file} (TRUNCATED: showing ~{actual_tokens} of ~{total_tokens} tokens, {file_size} bytes total):\n\n{truncated_content}\n\n---\n[OUTPUT TRUNCATED - Use read_log_paginated for full access to large files]"
                )]
        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file: {e}"
            )]

    elif name == "read_log_paginated":
        filename = arguments.get("filename")
        start_line = arguments.get("start_line", 1)
        max_tokens = arguments.get("max_tokens", 4000)
        num_lines = arguments.get("num_lines")  # Optional, for backward compatibility
        expected_size = arguments.get("expected_size")
        expected_mtime = arguments.get("expected_mtime")

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        # Validate parameters
        if start_line < 1:
            return [TextContent(
                type="text",
                text="Error: start_line must be >= 1"
            )]

        # Backward compatibility: if num_lines specified, use line-based mode
        use_line_mode = num_lines is not None

        if use_line_mode:
            if num_lines < 1 or num_lines > 1000:
                return [TextContent(
                    type="text",
                    text="Error: num_lines must be between 1 and 1000"
                )]
        else:
            if max_tokens < 1 or max_tokens > 100000:
                return [TextContent(
                    type="text",
                    text="Error: max_tokens must be between 1 and 100000"
                )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        # Get file metadata for change detection
        try:
            file_stat = log_file.stat()
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting file stats: {e}"
            )]

        # Check if file changed since last read
        warnings = []
        if expected_size is not None and expected_size != file_size:
            size_diff = file_size - expected_size
            warnings.append(
                f"⚠️  FILE SIZE CHANGED: Expected {expected_size} bytes, now {file_size} bytes "
                f"({'+' if size_diff > 0 else ''}{size_diff} bytes). "
                f"File was modified during pagination - line numbers may be inconsistent!"
            )

        if expected_mtime is not None and abs(expected_mtime - file_mtime) > 0.001:
            warnings.append(
                f"⚠️  FILE MODIFIED: Modification time changed. "
                f"File was modified during pagination - line numbers may be inconsistent!"
            )

        try:
            with open(log_file, 'r') as f:
                # Read all lines to count total
                all_lines = f.readlines()
                total_lines = len(all_lines)

                if use_line_mode:
                    # Line-based mode (backward compatibility)
                    end_line = min(start_line - 1 + num_lines, total_lines)
                    lines = all_lines[start_line - 1:end_line]
                    mode_info = f"Line-based mode: {num_lines} lines"
                else:
                    # Token-based mode (default)
                    # Estimate ~4 chars per token
                    lines = []
                    estimated_tokens = 0
                    current_idx = start_line - 1

                    while current_idx < total_lines and estimated_tokens < max_tokens:
                        line = all_lines[current_idx]
                        line_tokens = len(line) // 4  # Rough estimation: 4 chars per token

                        # Always include at least one line
                        if lines or estimated_tokens + line_tokens <= max_tokens:
                            lines.append(line)
                            estimated_tokens += line_tokens
                            current_idx += 1
                        else:
                            break

                    end_line = start_line - 1 + len(lines)
                    mode_info = f"Token-based mode: ~{estimated_tokens} tokens (~{max_tokens} max)"

                # Build result with file metadata
                result = ""

                # Show warnings first if any
                if warnings:
                    result += "\n".join(warnings) + "\n\n"

                result += f"File: {log_file}\n"
                result += f"File size: {file_size} bytes\n"
                result += f"File mtime: {file_mtime}\n"
                result += f"Total lines: {total_lines}\n"
                result += f"Showing lines {start_line}-{start_line - 1 + len(lines)} ({len(lines)} lines)\n"
                result += f"Mode: {mode_info}\n"
                result += f"\n{'=' * 60}\n\n"

                for i, line in enumerate(lines, start=start_line):
                    result += f"{i:6d} | {line}"

                if end_line < total_lines:
                    result += f"\n\n... {total_lines - end_line} more lines available (continue from line {end_line + 1}) ...\n"
                    result += f"\nFor next call, use: start_line={end_line + 1}, expected_size={file_size}, expected_mtime={file_mtime}"

                return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file: {e}"
            )]

    elif name == "search_log_file":
        filename = arguments.get("filename")
        pattern = arguments.get("pattern")
        context_lines = arguments.get("context_lines", 2)
        context_before = arguments.get("context_before")
        context_after = arguments.get("context_after")
        case_sensitive = arguments.get("case_sensitive", False)
        max_tokens = arguments.get("max_tokens", 4000)
        max_matches = arguments.get("max_matches")  # Optional, for backward compatibility
        skip_matches = arguments.get("skip_matches", 0)

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        if not pattern:
            return [TextContent(
                type="text",
                text="Error: pattern parameter is required"
            )]

        # Determine actual context values
        # context_before/context_after override context_lines if specified
        if context_before is None:
            context_before = context_lines
        if context_after is None:
            context_after = context_lines

        # Validate parameters
        if context_before < 0 or context_before > 10:
            return [TextContent(
                type="text",
                text="Error: context_before must be between 0 and 10"
            )]

        if context_after < 0 or context_after > 10:
            return [TextContent(
                type="text",
                text="Error: context_after must be between 0 and 10"
            )]

        # Backward compatibility: if max_matches specified, use match-based mode
        use_match_mode = max_matches is not None

        if use_match_mode:
            if max_matches < 1 or max_matches > 500:
                return [TextContent(
                    type="text",
                    text="Error: max_matches must be between 1 and 500"
                )]
        else:
            if max_tokens < 1 or max_tokens > 100000:
                return [TextContent(
                    type="text",
                    text="Error: max_tokens must be between 1 and 100000"
                )]

        if skip_matches < 0:
            return [TextContent(
                type="text",
                text="Error: skip_matches must be >= 0"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        # Compile regex pattern
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            return [TextContent(
                type="text",
                text=f"Error: Invalid regex pattern: {e}"
            )]

        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                total_lines = len(lines)

                # Find all matches
                matches = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        matches.append(i)

                total_matches = len(matches)

                if total_matches == 0:
                    return [TextContent(
                        type="text",
                        text=f"No matches found for pattern: {pattern}"
                    )]

                # Skip matches based on skip_matches parameter
                matches_to_process = matches[skip_matches:]

                if not matches_to_process:
                    return [TextContent(
                        type="text",
                        text=f"No more matches (total: {total_matches}, skipped: {skip_matches})"
                    )]

                # Collect matches based on mode (token-based or match-based)
                paginated_matches = []
                estimated_tokens = 0

                if use_match_mode:
                    # Match-based mode (backward compatibility)
                    paginated_matches = matches_to_process[:max_matches]
                    mode_info = f"Match-based mode: {len(paginated_matches)} matches"
                else:
                    # Token-based mode (default)
                    # Estimate tokens for each match with its context
                    for match_idx in matches_to_process:
                        # Calculate context range
                        start = max(0, match_idx - context_before)
                        end = min(total_lines, match_idx + context_after + 1)

                        # Estimate tokens for this match and its context
                        match_text = ""
                        for i in range(start, end):
                            line_num = i + 1
                            marker = ">>>" if i == match_idx else "   "
                            match_text += f"{marker} {line_num:6d} | {lines[i]}"
                        match_text += f"\n{'-' * 60}\n\n"

                        match_tokens = len(match_text) // 4  # Rough estimation: 4 chars per token

                        # Always include at least one match
                        if not paginated_matches or estimated_tokens + match_tokens <= max_tokens:
                            paginated_matches.append(match_idx)
                            estimated_tokens += match_tokens
                        else:
                            break

                    mode_info = f"Token-based mode: ~{estimated_tokens} tokens (~{max_tokens} max)"

                # Build result
                result = f"File: {log_file}\n"
                result += f"Pattern: {pattern}\n"
                result += f"Total matches: {total_matches}\n"
                result += f"Showing matches {skip_matches + 1}-{skip_matches + len(paginated_matches)}\n"
                if context_before == context_after:
                    result += f"Context lines: {context_before}\n"
                else:
                    result += f"Context: {context_before} before, {context_after} after\n"
                result += f"Mode: {mode_info}\n"
                result += f"\n{'=' * 60}\n\n"

                for match_idx in paginated_matches:
                    # Calculate context range
                    start = max(0, match_idx - context_before)
                    end = min(total_lines, match_idx + context_after + 1)

                    # Show context
                    for i in range(start, end):
                        line_num = i + 1
                        marker = ">>>" if i == match_idx else "   "
                        result += f"{marker} {line_num:6d} | {lines[i]}"

                    result += f"\n{'-' * 60}\n\n"

                if skip_matches + len(paginated_matches) < total_matches:
                    remaining = total_matches - (skip_matches + len(paginated_matches))
                    result += f"... {remaining} more matches available ...\n"
                    result += f"\nFor next call, use: skip_matches={skip_matches + len(paginated_matches)}"

                return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error searching file: {e}"
            )]

    elif name == "head_log":
        filename = arguments.get("filename")
        max_tokens = min(arguments.get("max_tokens", 4000), 100000)
        num_lines = arguments.get("lines")  # Optional line limit

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        try:
            all_lines = log_file.read_text().splitlines(keepends=True)
            file_size = log_file.stat().st_size
            total_lines = len(all_lines)

            # Read lines from beginning
            lines = []
            estimated_tokens = 0
            truncated_by = None

            for idx, line in enumerate(all_lines):
                # Check line limit first
                if num_lines is not None and len(lines) >= num_lines:
                    truncated_by = "lines"
                    break
                # Check token limit
                line_tokens = len(line) // 4
                if lines and estimated_tokens + line_tokens > max_tokens:
                    truncated_by = "tokens"
                    break
                lines.append(line)
                estimated_tokens += line_tokens

            lines_read = len(lines)

            result = f"Head of {log_file}\n"
            result += f"File size: {file_size} bytes, {total_lines} lines total\n"
            if num_lines is not None:
                result += f"Showing: lines 1-{lines_read} (requested: {num_lines} lines, ~{estimated_tokens} tokens)\n"
            else:
                result += f"Showing: lines 1-{lines_read} (~{estimated_tokens} tokens)\n"
            result += f"\n{'=' * 60}\n\n"

            # Add line numbers
            for i, line in enumerate(lines, 1):
                result += f"{i:6d} | {line}"

            if lines_read < total_lines:
                result += f"\n{'=' * 60}\n"
                result += f"... {total_lines - lines_read} more lines available ...\n"
                result += f"Use read_log_range with start_line={lines_read + 1} to continue"

            return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file: {e}"
            )]

    elif name == "tail_log":
        filename = arguments.get("filename")
        max_tokens = min(arguments.get("max_tokens", 4000), 100000)
        num_lines = arguments.get("lines")  # Optional line limit

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        try:
            all_lines = log_file.read_text().splitlines(keepends=True)
            file_size = log_file.stat().st_size
            total_lines = len(all_lines)

            # Read lines from end
            lines = []
            estimated_tokens = 0

            for line in reversed(all_lines):
                # Check line limit first
                if num_lines is not None and len(lines) >= num_lines:
                    break
                # Check token limit
                line_tokens = len(line) // 4
                if lines and estimated_tokens + line_tokens > max_tokens:
                    break
                lines.insert(0, line)
                estimated_tokens += line_tokens

            lines_read = len(lines)
            start_line = total_lines - lines_read + 1

            result = f"Tail of {log_file}\n"
            result += f"File size: {file_size} bytes, {total_lines} lines total\n"
            if num_lines is not None:
                result += f"Showing: lines {start_line}-{total_lines} (requested: {num_lines} lines, ~{estimated_tokens} tokens)\n"
            else:
                result += f"Showing: lines {start_line}-{total_lines} (~{estimated_tokens} tokens)\n"
            result += f"\n{'=' * 60}\n\n"

            # Add line numbers
            for i, line in enumerate(lines, start_line):
                result += f"{i:6d} | {line}"

            if lines_read < total_lines:
                result += f"\n{'=' * 60}\n"
                result += f"... {total_lines - lines_read} earlier lines available ...\n"
                result += f"Use read_log_range or head_log to see earlier content"

            return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file: {e}"
            )]

    elif name == "read_log_range":
        filename = arguments.get("filename")
        start_line = arguments.get("start_line", 1)
        end_line = arguments.get("end_line")  # Optional, None means to end or token limit
        max_tokens = min(arguments.get("max_tokens", 4000), 100000)

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        if start_line < 1:
            return [TextContent(
                type="text",
                text="Error: start_line must be >= 1"
            )]

        if end_line is not None and end_line < start_line:
            return [TextContent(
                type="text",
                text="Error: end_line must be >= start_line"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        try:
            all_lines = log_file.read_text().splitlines(keepends=True)
            file_size = log_file.stat().st_size
            total_lines = len(all_lines)

            if start_line > total_lines:
                return [TextContent(
                    type="text",
                    text=f"Error: start_line {start_line} exceeds file length ({total_lines} lines)"
                )]

            # Determine effective end line
            effective_end = end_line if end_line is not None else total_lines
            effective_end = min(effective_end, total_lines)

            # Read lines in range, respecting token limit
            lines = []
            estimated_tokens = 0
            actual_end = start_line - 1  # Will be updated as we read

            for idx in range(start_line - 1, effective_end):
                line = all_lines[idx]
                line_tokens = len(line) // 4
                if lines and estimated_tokens + line_tokens > max_tokens:
                    break
                lines.append(line)
                estimated_tokens += line_tokens
                actual_end = idx + 1  # 1-based line number

            lines_read = len(lines)

            result = f"Range from {log_file}\n"
            result += f"File size: {file_size} bytes, {total_lines} lines total\n"
            if end_line is not None:
                result += f"Requested: lines {start_line}-{end_line}\n"
            result += f"Showing: lines {start_line}-{actual_end} (~{estimated_tokens} tokens)\n"
            result += f"\n{'=' * 60}\n\n"

            # Add line numbers
            for i, line in enumerate(lines, start_line):
                result += f"{i:6d} | {line}"

            # Check if there's more content
            if actual_end < total_lines:
                result += f"\n{'=' * 60}\n"
                if end_line is not None and actual_end < end_line:
                    remaining_requested = end_line - actual_end
                    result += f"... {remaining_requested} more lines in requested range (truncated by token limit) ...\n"
                else:
                    result += f"... {total_lines - actual_end} more lines in file ...\n"
                result += f"Use read_log_range with start_line={actual_end + 1} to continue"

            return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading file: {e}"
            )]

    elif name == "find_errors":
        filename = arguments.get("filename")
        context_lines = min(arguments.get("context_lines", 2), 10)
        include_warnings = arguments.get("include_warnings", False)
        max_tokens = min(arguments.get("max_tokens", 4000), 100000)

        if not filename:
            return [TextContent(
                type="text",
                text="Error: filename parameter is required"
            )]

        try:
            log_dir, log_file = resolve_log_file(filename)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {e}"
            )]

        if not log_file.exists():
            return [TextContent(
                type="text",
                text=f"Log file does not exist: {log_file}"
            )]

        if not log_file.is_file():
            return [TextContent(
                type="text",
                text=f"Path exists but is not a file: {log_file}"
            )]

        # Common error patterns in software development
        error_patterns = [
            # General error levels
            r'\bERROR\b',
            r'\bFATAL\b',
            r'\bCRITICAL\b',
            r'\bSEVERE\b',
            # Exception patterns
            r'\bException\b',
            r'\bError:',
            r'\bTraceback\b',
            r'^\s*at\s+.*\(.*:\d+\)',  # Stack trace lines
            r'^\s*File\s+".*",\s+line\s+\d+',  # Python traceback
            # Failure patterns
            r'\bFAIL(ED|URE)?\b',
            r'\bfailed\b',
            r'\bAborted\b',
            # Language-specific
            r'\bpanic\b',  # Go, Rust
            r'\bNullPointerException\b',
            r'\bSegmentation fault\b',
            r'\bcore dumped\b',
            r'\bOOM\b',  # Out of memory
            r'\bOutOfMemory\b',
            # HTTP errors
            r'\b[45]\d{2}\s+(error|Error|ERROR)',
            r'HTTP[/\s]+[12]\.[01]\s+[45]\d{2}',
            # Exit codes
            r'exit(ed)?\s+(with\s+)?(code|status)\s+[1-9]',
            r'return(ed)?\s+(-?[1-9]\d*|non-?zero)',
            # Assertions
            r'\bAssertionError\b',
            r'\bassertion\s+failed\b',
        ]

        if include_warnings:
            error_patterns.extend([
                r'\bWARN(ING)?\b',
                r'\bwarn(ing)?\b',
                r'\bCaution\b',
                r'\bDeprecated\b',
            ])

        # Compile combined pattern (case-insensitive for some)
        combined_pattern = '|'.join(f'({p})' for p in error_patterns)

        try:
            lines = log_file.read_text().splitlines(keepends=True)
            file_size = log_file.stat().st_size
            total_lines = len(lines)

            # Find matching lines
            error_indices = []
            for idx, line in enumerate(lines):
                if re.search(combined_pattern, line, re.IGNORECASE):
                    error_indices.append(idx)

            if not error_indices:
                return [TextContent(
                    type="text",
                    text=f"No errors found in {log_file}\nFile size: {file_size} bytes, {total_lines} lines\nPatterns searched: ERROR, Exception, FATAL, Failed, Traceback, panic, etc." +
                         ("\nNote: Warnings not included. Use include_warnings=true to include them." if not include_warnings else "")
                )]

            # Build output with context, respecting token limit
            result = f"Errors in {log_file}\n"
            result += f"File size: {file_size} bytes, {total_lines} lines\n"
            result += f"Found {len(error_indices)} error lines" + (" (including warnings)" if include_warnings else "") + "\n"
            result += f"Context: {context_lines} lines before/after\n"
            result += f"\n{'=' * 60}\n\n"

            estimated_tokens = len(result) // 4
            shown_errors = 0
            shown_indices = set()

            for error_idx in error_indices:
                # Calculate context range
                start = max(0, error_idx - context_lines)
                end = min(total_lines, error_idx + context_lines + 1)

                # Build this error block
                block = ""
                for i in range(start, end):
                    if i in shown_indices:
                        continue  # Skip already shown lines
                    line_num = i + 1
                    marker = ">>>" if i == error_idx else "   "
                    block += f"{marker} {line_num:6d} | {lines[i]}"
                    shown_indices.add(i)

                block += f"\n{'-' * 60}\n\n"
                block_tokens = len(block) // 4

                # Check token limit
                if shown_errors > 0 and estimated_tokens + block_tokens > max_tokens:
                    remaining = len(error_indices) - shown_errors
                    result += f"... {remaining} more errors (token limit reached) ...\n"
                    result += f"Use search_log_file with specific patterns for more details"
                    break

                result += block
                estimated_tokens += block_tokens
                shown_errors += 1

            if shown_errors == len(error_indices):
                result += f"[All {shown_errors} errors shown]\n"

            return [TextContent(type="text", text=result)]

        except PermissionError:
            return [TextContent(
                type="text",
                text=f"Permission denied reading: {log_file}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error searching file: {e}"
            )]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run():
    """Entry point for the log-mcp command."""
    global LOG_DIRECTORIES

    parser = argparse.ArgumentParser(
        description="MCP server for inspecting log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Log directory priority (highest to lowest):
  1. --log-dir command line arguments (can specify multiple)
  2. LOG_MCP_DIR environment variable (colon-separated paths)
  3. $XDG_RUNTIME_DIR/log (default)

Examples:
  log-mcp                                        # Use default $XDG_RUNTIME_DIR/log
  log-mcp --log-dir /var/log                    # Use single custom directory
  log-mcp --log-dir /var/log --log-dir /tmp/logs  # Use multiple directories
  LOG_MCP_DIR=/var/log:/tmp/logs log-mcp        # Use environment variable (colon-separated)
        """
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        action="append",
        dest="log_dirs",
        help="Add a log directory to search (can be specified multiple times)"
    )

    args = parser.parse_args()

    if args.log_dirs:
        LOG_DIRECTORIES = args.log_dirs
        # Validate directories exist
        for log_dir in LOG_DIRECTORIES:
            if not Path(log_dir).exists():
                print(f"Warning: Log directory does not exist: {log_dir}", file=sys.stderr)

    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    run()
