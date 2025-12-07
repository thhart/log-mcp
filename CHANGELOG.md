# Changelog

All notable changes to this project will be documented in this file.

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
