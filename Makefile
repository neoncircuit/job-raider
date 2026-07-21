# Job Raider - Makefile
# Convenient commands for development

.PHONY: help dev dev-api dev-frontend install install-frontend test lint format clean \
        docker-build docker-up docker-down docker-logs docker-restart type-check

# Default target
help:
	@echo "Job Raider - Development Commands"
	@echo ""
	@echo "Local Development:"
	@echo "  make dev              - Start backend API + Next.js frontend concurrently"
	@echo "  make dev-api          - Start backend API only (port 8000)"
	@echo "  make dev-frontend     - Start Next.js dev server only (port 3000)"
	@echo ""
	@echo "Frontend:"
	@echo "  make install-frontend - Install / update frontend Node dependencies"
	@echo "  make type-check       - Run TypeScript type check on frontend"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        - Start all Docker containers"
	@echo "  make docker-build     - Build Docker images"
	@echo "  make docker-down      - Stop Docker containers"
	@echo "  make docker-logs      - View container logs"
	@echo ""
	@echo "Backend:"
	@echo "  make install          - Install / update Python dependencies"
	@echo "  make test             - Run backend test suite"
	@echo "  make lint             - Run ruff + mypy on backend"
	@echo "  make format           - Auto-format backend code"
	@echo "  make clean            - Remove build artefacts"
	@echo ""
	@echo "URLs (when running):"
	@echo "  Frontend:  http://localhost:3000"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo "  Health:    http://localhost:8000/api/health"

# ── Local dev ──────────────────────────────────────────────────────────────────

dev:
	@./scripts/dev.sh both

dev-api:
	@./scripts/dev.sh api

dev-frontend:
	@./scripts/dev.sh frontend

# ── Dependencies ───────────────────────────────────────────────────────────────

install:
	@echo "Installing Python dependencies..."
	@cd apps/backend-py && .venv/bin/pip install -r requirements.txt

install-frontend:
	@echo "Installing Node dependencies..."
	@cd apps/frontend-ts && npm ci

# ── Quality ────────────────────────────────────────────────────────────────────

test:
	@echo "Running backend tests..."
	@cd apps/backend-py && PYTHONPATH=. .venv/bin/python -m pytest tests/ -v

lint:
	@echo "Running Python linting..."
	@cd apps/backend-py && .venv/bin/python -m ruff check src/ tests/
	@cd apps/backend-py && .venv/bin/python -m mypy src/ --ignore-missing-imports --no-error-summary || true

format:
	@echo "Formatting Python code..."
	@cd apps/backend-py && .venv/bin/python -m black src/ tests/
	@cd apps/backend-py && .venv/bin/python -m ruff check --fix src/ tests/

type-check:
	@echo "Running TypeScript type check..."
	@cd apps/frontend-ts && npm run type-check

clean:
	@echo "Cleaning build artefacts..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true
	@rm -rf apps/frontend-ts/.next 2>/dev/null || true
	@rm -rf logs/*.log 2>/dev/null || true
	@echo "Clean complete"

# ── Docker ─────────────────────────────────────────────────────────────────────

docker-build:
	@echo "Building Docker images..."
	@docker compose build

docker-up:
	@echo "Starting Docker containers..."
	@./docker-run.sh

docker-down:
	@echo "Stopping Docker containers..."
	@docker compose down

docker-logs:
	@docker compose logs -f

docker-restart: docker-down docker-up
