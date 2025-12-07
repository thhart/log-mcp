# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2025-12-07

### Changed
- **Token-based pagination for `search_log_file`**: Now uses `max_tokens` (default: 4000) instead of `max_matches` for pagination
- `max_matches` parameter deprecated but still supported for backward compatibility
- Search results now show mode (token-based vs match-based) and estimated token count
- Improved pagination to respect AI context limits by estimating tokens for each match with its context

### Rationale
- Search results can be large when matches include context lines
- Token-based pagination provides more predictable memory usage for AI assistants
- Consistent with `read_log_paginated` pagination strategy
- Better user experience by avoiding context limit issues

## [0.2.5] - 2025-12-07

### Added
- File modification tracking for `read_log_paginated`
- `expected_size` and `expected_mtime` parameters to detect file changes during pagination
- Automatic warnings when log files are modified between pagination calls
- File metadata (size, mtime) included in all responses
- Helpful "For next call, use:" message with correct parameters

### Fixed
- Race condition when reading actively-written log files
- Inconsistent line numbers when files are modified during pagination

### Rationale
- Log files are often actively written to during debugging
- File changes between pagination calls cause line number shifts
- Detecting changes allows AI to restart from beginning or warn user
- Provides visibility into file state for better debugging

## [0.2.4] - 2025-12-07

### Changed
- **BREAKING (but backward compatible)**: `read_log_paginated` now uses token-based pagination instead of line-based
- Default pagination is now `max_tokens=4000` instead of `num_lines=100`
- Uses ~4 characters per token estimation for consistent context usage
- `num_lines` parameter deprecated but still supported for backward compatibility
- Output now shows mode (token-based vs line-based) and estimated token count

### Rationale
- Log lines vary drastically in length (10-10000+ characters)
- Token limits matter for AI context windows, not line counts
- Provides more predictable and useful pagination for AI assistants

## [0.2.3] - 2025-12-07

### Added
- `context_before` and `context_after` parameters for `search_log_file` tool
- Separate control of context lines before and after matches (like grep's -B and -A options)
- Support for asymmetric context display (e.g., 5 lines before, 2 lines after)

### Changed
- `context_lines` now serves as default for both before and after context
- Context display in search results shows separate before/after counts when different

## [0.2.2] - 2025-12-07

### Changed
- Package renamed to log-inspector-mcp for PyPI compatibility
- Updated GitHub repository URL in package metadata
- Documentation improvements for configuration examples

## [0.2.1] - 2025-12-07

### Changed
- Updated package metadata with author information
- Minor documentation improvements

## [0.2.0] - 2025-12-07

### Added
- `read_log_paginated` tool for reading large log files in chunks with line numbers
- `search_log_file` tool for regex-based searching with:
  - Configurable context lines (like grep -C)
  - Case-sensitive/insensitive search
  - Pagination support for search results
  - Visual markers (>>>) for matching lines
- Support for handling large log files efficiently
- **Multiple log directory support:**
  - `--log-dir` command-line argument (can be specified multiple times)
  - `LOG_MCP_DIR` environment variable (colon-separated paths)
  - `list_log_files` scans all configured directories
  - Auto-resolves filenames across all directories
- Configurable log directory with priority: CLI args > env var > default

### Changed
- Updated `runtime-logs` prompt to mention all 4 available tools and all directories
- Enhanced tool descriptions to guide when to use each tool
- Improved error messages when log directories are not accessible
- `list_log_files` now shows which directories are being scanned
- **Comprehensive README documentation:**
  - Added detailed "What is this?" section
  - Included use cases and workflow examples
  - Added application logging configuration for Node.js, Python, Java, Rust, and Go
  - Added IDE configuration examples (VSCode, IntelliJ/PyCharm)
  - Added example end-to-end debugging workflow

## [0.1.0] - 2025-12-07

### Added
- Initial release of log-mcp MCP server
- `list_log_files` tool to list all log files in $XDG_RUNTIME_DIR/log
- `get_log_content` tool to read specific log files
- `runtime-logs` prompt that automatically informs AI about log inspection capabilities
- Security checks to ensure file access is restricted to the log directory
- Proper pip-installable package structure with setuptools
- MIT License
- Comprehensive README with installation and usage instructions
- AI guidance system that proactively suggests log inspection when users report errors
