# TrialSync ETL Makefile
# Convenience targets for development and operations

.PHONY: help install test run run-sample-job run-all start-server start-scheduler clean

# Default target
help:
	@echo "TrialSync ETL - Available targets:"
	@echo ""
	@echo "  make install              - Install dependencies"
	@echo "  make test                  - Run tests"
	@echo "  make run JOB_ID=1        - Run a specific job"
	@echo "  make run-sample-job       - Run sample job (Job 1) in dry-run mode"
	@echo "  make run-all              - Run all active jobs"
	@echo "  make start-server         - Start the web server"
	@echo "  make start-scheduler     - Start the scheduler service"
	@echo "  make clean                - Clean Python cache files"
	@echo ""
	@echo "Environment variables:"
	@echo "  ENV=development|test|production  - Environment (default: development)"
	@echo "  DRY_RUN=true|false                - Dry run mode (default: true in dev/test)"
	@echo "  JOB_ID=<id>                       - Job ID to run"

# Environment detection
ENV ?= development
PYTHON ?= python3
VENV ?= .venv
VENV_BIN := $(VENV)/bin

# Install dependencies
install:
	@echo "Installing dependencies..."
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt
	@echo "✓ Dependencies installed"

# Run tests
test:
	@echo "Running tests..."
	$(VENV_BIN)/pytest -v --cov=src --cov-report=term-missing
	@echo "✓ Tests complete"

# Run a specific job
run:
	@if [ -z "$(JOB_ID)" ]; then \
		echo "Error: JOB_ID is required. Usage: make run JOB_ID=1"; \
		exit 1; \
	fi
	@echo "Running job $(JOB_ID) (ENV=$(ENV), DRY_RUN=$(DRY_RUN))..."
	@. $(VENV_BIN)/activate && \
		ENVIRONMENT=$(ENV) DRY_RUN=$(DRY_RUN) \
		trialsync-etl run --job-id $(JOB_ID) $(if $(findstring false,$(DRY_RUN)),,--dry-run)

# Run sample job (Job 1: Sites) in dry-run mode
run-sample-job:
	@echo "Running sample job (Job 1: Sites) in dry-run mode..."
	@. $(VENV_BIN)/activate && \
		ENVIRONMENT=$(ENV) DRY_RUN=true \
		trialsync-etl run --job-id 1 --dry-run

# Run all active jobs
run-all:
	@echo "Running all active jobs (ENV=$(ENV), DRY_RUN=$(DRY_RUN))..."
	@. $(VENV_BIN)/activate && \
		ENVIRONMENT=$(ENV) DRY_RUN=$(DRY_RUN) \
		trialsync-etl run --all $(if $(findstring false,$(DRY_RUN)),,--dry-run)

# Start web server
start-server:
	@echo "Starting web server..."
	@. $(VENV_BIN)/activate && \
		ENVIRONMENT=$(ENV) \
		python -m src.web.server

# Start scheduler service
start-scheduler:
	@echo "Starting scheduler service..."
	@. $(VENV_BIN)/activate && \
		ENVIRONMENT=$(ENV) \
		trialsync-etl scheduler

# Clean Python cache
clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	@echo "✓ Clean complete"

# Development helpers
dev-setup: install
	@echo "✓ Development environment ready"
	@echo "Run 'make run-sample-job' to test"

# Check code quality
lint:
	@echo "Running linters..."
	$(VENV_BIN)/flake8 src tests
	$(VENV_BIN)/black --check src tests
	$(VENV_BIN)/mypy src

# Format code
format:
	@echo "Formatting code..."
	$(VENV_BIN)/black src tests
	$(VENV_BIN)/isort src tests

