# Project Standards (Python & Ruff)

## Tech Stack & Standards
- **Runtime**: Python 3.10+ (use `|` for unions, `kw_only=True` for dataclasses).
- **Validation**: Strict Pydantic v2 (do not write deprecated v1 code).
- **Async**: Use `asyncio` for I/O; avoid blocking calls in async contexts.
- **Typing**: Strict type hints required for all function signatures and public attributes.
- **Path Handling**: Use `pathlib` instead of `os.path`.
- **Formatting**: Format-on-save is system-handled; do not run manual `ruff format` commands.
- **Coding Style**: Use F-strings only. Prefer list/dict comprehensions over simple loops. Use Google-style docstrings only if logic is complex.

## Commands & Verification
- **External Calls**: Always mock external API calls and DB connections in tests.

## Test Execution Guardrails (CRITICAL)
- **Do NOT run tests** if changes are restricted to non-code files (such as `.gitignore`, `*.md`, `*.json`, configs) or Git operations.
- **Do NOT run tests for minor edits.** Skip test execution completely if code changes are superficial or localized, including:
  - Fixing typos in string literals, variables, or error messages.
  - Modifying logs, `print` statements, warning strings, or exception messages.
  - Adding, editing, or formatting comments, docstrings, or type hints.
  - Cosmetic code formatting (spacing, line breaks, reordering imports).
- **Run tests ONLY for significant functional modifications:** Execute tests only when structural logic changes, new features, API endpoints, complex algorithms, or the test files themselves are modified.

## Agent Guardrails
- **FastAPI / Pydantic v2**: If there is any syntactic ambiguity, use `websearch` immediately instead of guessing.
- **No Placeholder Code**: Never write `# TODO` or leave incomplete logic/mocks.
