# AGENTS.md

This file provides context and guidelines for AI agents working on the `xyz-dl` codebase.

## 1. Project Overview
`xyz-dl` is a Python CLI tool for downloading podcasts from [Xiaoyuzhou FM](https://www.xiaoyuzhoufm.com).
It supports downloading single episodes, full podcasts, and managing metadata.

## 2. Environment & Build

### Dependency Management
- The project uses `uv` for dependency management.
- Python version: `>=3.13`
- Configuration file: `pyproject.toml`

### Key Commands
- **Install dependencies:**
  ```bash
  uv sync
  ```
- **Run application:**
  ```bash
  uv run main.py [args]
  # Example: uv run main.py --help
  ```
- **Build executable (Windows):**
  ```powershell
  .\build.ps1
  # OR manually:
  # uv run -m PyInstaller -F --name xyz-dl main.py
  ```

## 3. Code Style & Conventions

### General
- **Language:** Python
- **Comments/Docstrings:** MUST be in **Chinese (Simplified)**.
- **Type Hints:** MANDATORY for all function signatures (e.g., `def func(a: int) -> str:`).
- **Path Handling:** Use `pathlib.Path` instead of `os.path`.

### Formatting
- **Indent:** 4 spaces.
- **Line Length:** Follow PEP 8 (approx 88-100 chars).
- **Imports:** Grouped:
  1. Standard Library
  2. Third-party (`requests`, `tqdm`)
  3. Local application (`auth`, `config`, `utils`)

### User Interface / Logging
- **Emojis:** Use emojis in `print` output to denote status:
  - `✅` Success
  - `❌` Error/Failure
  - `🚀` Start/Progress
  - `⚠️` Warning
  - `🔍` Checking/Searching
  - `📊` Stats/Limit
  - `📁` File/Directory
  - `🔐` Auth/Login
  - `🎉` Completion
- **Output:** Use `print()` for CLI output. Ensure user-facing messages are friendly and helpful.

### Error Handling
- Use `try...except` blocks for network and I/O operations.
- Catch `Exception` in top-level handlers and print user-friendly error messages (prefixed with `❌`).
- Do not show raw tracebacks to the user unless debugging.

## 4. Testing
- **Current Status:** No existing test suite found.
- **New Tests:** If adding logic, create tests using `pytest` (not yet in dependencies, add if needed).
- **Test Location:** Create a `tests/` directory if adding tests.

## 5. Project Structure
- `main.py`: Entry point and CLI argument parsing.
- `auth.py`: Handles user login and token management (`XiaoyuzhouAuth`).
- `downloader.py`: Core download logic (`XiaoyuzhouDownloader`).
- `config.py`: Configuration management.
- `utils.py`: Helper functions (filename sanitization, URL parsing).
- `api.py`: API wrapper (presumed).
- `xyz-config.json`: Runtime configuration storage.

## 6. Implementation Details
- **Input Detection:** Logic in `utils.py` detects if input is a Podcast ID, Episode ID, or URL.
- **Config:** Stored in `xyz-config.json`.
- **Auth:** Mobile number login flow. Tokens stored locally.

## 7. Cursor / Copilot Rules
*No specific rules found in `.cursor/rules/` or `.github/copilot-instructions.md`.*
*Follow standard Python best practices and the style guide above.*
