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
- **Run Tests**: Use `pytest`. Do not use `poetry run pytest` unless specifically instructed.
- **External Calls**: Always mock external API calls and DB connections in tests.

## Agent Guardrails
- **FastAPI / Pydantic v2**: If there is any syntactic ambiguity, use `websearch` immediately instead of guessing.
- **No Placeholder Code**: Never write `# TODO` or leave incomplete logic/mocks.
