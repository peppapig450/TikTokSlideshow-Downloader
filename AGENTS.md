# Repository Guidelines

## Python Formatting and Testing

- Use the configuration in `pyproject.toml` for all Python code.
- Before committing any changes to Python files, run:
  - `uv run ruff format .`
  - `uv run ruff check --fix .`
  - `uv run mypy .`
  - `uv run pytest`
- The maximum line length is 100 characters as specified in `[tool.ruff]`.

## Project Layout

- Source code resides in `tiktok_downloader/`.
- Tests live in the `tests/` directory.

## Pull Requests and Commits

- Pull request messages must summarize code changes and link to any failing checks.
- All commit messages should follow the **conventional commits** style.
