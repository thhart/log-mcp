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
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="read_log_paginated",
            description="Reads a paginated portion of a log file. Useful for large log files. Returns specific line ranges.",
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
                    "num_lines": {
                        "type": "integer",
                        "description": "Number of lines to read (default: 100, max: 1000)",
                        "default": 100
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="search_log_file",
            description="Searches a log file using regex pattern and returns matching lines with surrounding context. Supports pagination of results.",
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
                        "description": "Number of lines to show before and after each match (default: 2, max: 10)",
                        "default": 2
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: false)",
                        "default": False
                    },
                    "max_matches": {
                        "type": "integer",
                        "description": "Maximum number of matches to return (default: 50, max: 500)",
                        "default": 50
                    },
                    "skip_matches": {
                        "type": "integer",
                        "description": "Number of matches to skip (for pagination, default: 0)",
                        "default": 0
                    }
                },
                "required": ["filename", "pattern"]
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
            return [TextContent(
                type="text",
                text=f"Content of {log_file}:\n\n{content}"
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
        num_lines = arguments.get("num_lines", 100)

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

        if num_lines < 1 or num_lines > 1000:
            return [TextContent(
                type="text",
                text="Error: num_lines must be between 1 and 1000"
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
            with open(log_file, 'r') as f:
                # Read all lines to count total
                all_lines = f.readlines()
                total_lines = len(all_lines)

                # Calculate the slice
                end_line = min(start_line - 1 + num_lines, total_lines)
                lines = all_lines[start_line - 1:end_line]

                result = f"File: {log_file}\n"
                result += f"Total lines: {total_lines}\n"
                result += f"Showing lines {start_line}-{start_line - 1 + len(lines)}\n"
                result += f"\n{'=' * 60}\n\n"

                for i, line in enumerate(lines, start=start_line):
                    result += f"{i:6d} | {line}"

                if end_line < total_lines:
                    result += f"\n\n... {total_lines - end_line} more lines available ..."

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
        case_sensitive = arguments.get("case_sensitive", False)
        max_matches = arguments.get("max_matches", 50)
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

        # Validate parameters
        if context_lines < 0 or context_lines > 10:
            return [TextContent(
                type="text",
                text="Error: context_lines must be between 0 and 10"
            )]

        if max_matches < 1 or max_matches > 500:
            return [TextContent(
                type="text",
                text="Error: max_matches must be between 1 and 500"
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

                # Apply pagination
                paginated_matches = matches[skip_matches:skip_matches + max_matches]

                if not paginated_matches:
                    return [TextContent(
                        type="text",
                        text=f"No more matches (total: {total_matches}, skipped: {skip_matches})"
                    )]

                result = f"File: {log_file}\n"
                result += f"Pattern: {pattern}\n"
                result += f"Total matches: {total_matches}\n"
                result += f"Showing matches {skip_matches + 1}-{skip_matches + len(paginated_matches)}\n"
                result += f"Context lines: {context_lines}\n"
                result += f"\n{'=' * 60}\n\n"

                for match_idx in paginated_matches:
                    # Calculate context range
                    start = max(0, match_idx - context_lines)
                    end = min(total_lines, match_idx + context_lines + 1)

                    # Show context
                    for i in range(start, end):
                        line_num = i + 1
                        marker = ">>>" if i == match_idx else "   "
                        result += f"{marker} {line_num:6d} | {lines[i]}"

                    result += f"\n{'-' * 60}\n\n"

                if skip_matches + len(paginated_matches) < total_matches:
                    remaining = total_matches - (skip_matches + len(paginated_matches))
                    result += f"... {remaining} more matches available (use skip_matches={skip_matches + len(paginated_matches)}) ..."

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
