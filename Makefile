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
	@echo "Starting backend API and Next.js frontend..."
	@(trap 'kill 0' SIGINT; \
	  cd backend-py && PYTHONPATH=. .venv/bin/python -m uvicorn src.api.main:app \
	    --host 0.0.0.0 --port 8000 --reload & \
	  cd frontend-ts && npm run dev -- --port 3000; \
	  wait)

dev-api:
	@echo "Starting backend API (port 8000)..."
	@mkdir -p logs
	@cd backend-py && PYTHONPATH=. .venv/bin/python -m uvicorn src.api.main:app \
		--host 0.0.0.0 --port 8000 --reload

dev-frontend:
	@echo "Starting Next.js dev server (port 3000)..."
	@cd frontend-ts && npm run dev -- --port 3000

# ── Dependencies ───────────────────────────────────────────────────────────────

install:
	@echo "Installing Python dependencies..."
	@cd backend-py && .venv/bin/pip install -r requirements.txt

install-frontend:
	@echo "Installing Node dependencies..."
	@cd frontend-ts && npm ci

# ── Quality ────────────────────────────────────────────────────────────────────

test:
	@echo "Running backend tests..."
	@cd backend-py && PYTHONPATH=. .venv/bin/python -m pytest tests/ -v

lint:
	@echo "Running Python linting..."
	@cd backend-py && .venv/bin/python -m ruff check src/
	@cd backend-py && .venv/bin/python -m mypy src/

format:
	@echo "Formatting Python code..."
	@cd backend-py && .venv/bin/python -m black src/
	@cd backend-py && .venv/bin/python -m ruff check --fix src/

type-check:
	@echo "Running TypeScript type check..."
	@cd frontend-ts && npm run type-check

clean:
	@echo "Cleaning build artefacts..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true
	@rm -rf frontend-ts/.next 2>/dev/null || true
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
