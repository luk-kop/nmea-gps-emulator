# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12+ package using a `src/` layout. Runtime code lives in `src/nmea_gps_emulator/`; the CLI entry point is `__main__.py`, core emulator behavior is in `main.py`, `nmea_gps.py`, and `custom_thread.py`, and parsing/validation helpers are in `validators.py`, `types.py`, `utils.py`, and `constants.py`. Tests live in `tests/` and are organized by behavior, for example `test_cli_parsing.py`, `test_cli_integration.py`, and `test_input_validation.py`. Project configuration is in `pyproject.toml`; locked dependencies are in `uv.lock`; CI and PR checks are under `.github/workflows/`.

## Build, Test, and Development Commands

- `make sync`: create or update the uv environment with runtime and development dependencies.
- `make run ARGS="--help"`: run the emulator CLI from the local uv environment; pass CLI options through `ARGS`.
- `make test`: run tests with coverage, matching CI.
- `make lint`: run Ruff lint checks.
- `make format`: format Python files.
- `make typecheck`: run the CI type check.
- `make check`: run lint, format check, type check, and tests.
- `make build`: build source and wheel distributions.
- `make audit`: run dependency vulnerability checks.
- `make pre-commit`: install local pre-commit hooks.

## Coding Style & Naming Conventions

Use Ruff as the formatter and linter. The configured style is 120-character lines, double quotes, spaces for indentation, Python 3.12 syntax, import sorting through Ruff, and `pep257` pydocstyle rules. Prefer typed functions and clear module-level boundaries. Use `snake_case` for functions, variables, and modules; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep CLI validation errors explicit and user-facing.

## Testing Guidelines

Tests use `pytest`, standard `unittest` classes, and Hypothesis property tests. Name test files `test_*.py` and test methods `test_*`. Add regression tests near the behavior being changed, especially for CLI parsing, input validation, NMEA sentence formatting, networking modes, and boundary values.

## Commit & Pull Request Guidelines

History and PR validation use semantic prefixes such as `ci:`, `docs:`, `fix:`, `test:`, `refactor:`, and `chore:`. Branch names must start with one of `feature/`, `feat/`, `fix/`, `bugfix/`, `hotfix/`, `docs/`, `chore/`, `refactor/`, `test/`, `release/`, `ci/`, or `dependabot/`. PRs require a non-empty description, a semantic title, passing CI, and no files over 10 MB. Link related issues when applicable and include CLI output or screenshots only when they clarify behavior changes.

## Security & Configuration Tips

Do not commit private keys, credentials, serial device details, or local environment files. Pre-commit runs secret and large-file checks; install it with `make pre-commit` before contributing.
