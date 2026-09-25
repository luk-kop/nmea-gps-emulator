PYTHON ?= python3.12
SRC_DIR := src/nmea_gps_emulator
TEST_DIR := tests
UV_RUN := uv run --python $(PYTHON) --extra dev

.PHONY: help install sync test lint format format-check typecheck check build run audit clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-14s %s\n", $$1, $$2}'

install: sync ## Create/update the uv environment with development dependencies.

sync: ## Sync runtime and development dependencies with uv.
	uv sync --python $(PYTHON) --extra dev

test: ## Run the test suite with coverage.
	$(UV_RUN) pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=xml

lint: ## Run Ruff lint checks.
	$(UV_RUN) ruff check $(SRC_DIR) $(TEST_DIR)

format: ## Format Python source and tests with Ruff.
	$(UV_RUN) ruff format $(SRC_DIR) $(TEST_DIR)

format-check: ## Check formatting without rewriting files.
	$(UV_RUN) ruff format --check $(SRC_DIR) $(TEST_DIR)

typecheck: ## Run mypy against package sources.
	$(UV_RUN) python -m mypy $(SRC_DIR) --ignore-missing-imports

check: lint format-check typecheck test ## Run the same core checks expected before a PR.

build: ## Build source and wheel distributions.
	uv build

run: ## Run the emulator CLI from the local environment.
	uv run --python $(PYTHON) python -m nmea_gps_emulator $(ARGS)

audit: ## Run dependency vulnerability checks.
	$(UV_RUN) pip-audit --skip-editable

clean: ## Remove virtual environments and generated files.
	rm -rf .venv venv dist htmlcov .pytest_cache .mypy_cache .ruff_cache .hypothesis
	rm -f .coverage coverage.xml
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
