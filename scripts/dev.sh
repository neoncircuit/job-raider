#!/bin/bash
# Job Raider - Dev Launcher with Self-Healing Dependencies
#
# Pre-flight checks: creates missing venv / node_modules before starting
# services. Keeps existing deps untouched if they already exist.
#
# Usage:
#   ./scripts/dev.sh              # Start both backend + frontend
#   ./scripts/dev.sh api          # Backend only (port 8000)
#   ./scripts/dev.sh frontend     # Frontend only (port 3000)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend-py"
FRONTEND_DIR="$PROJECT_ROOT/frontend-ts"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python3"

# --- Helpers ----------------------------------------------------------------

info()  { echo -e "\033[0;32m[OK]\033[0m $1"; }
warn()  { echo -e "\033[1;33m[!!]\033[0m $1"; }

# --- Backend dependency check -----------------------------------------------

ensure_backend() {
    if [ -x "$VENV_PYTHON" ]; then
        info "Backend venv ready"
        return
    fi

    warn "Backend .venv not found -- creating and installing dependencies..."

    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 not found. Install Python 3.10+ first."
        exit 1
    fi

    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install -q --upgrade pip setuptools wheel

    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        "$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
    else
        echo "Error: backend-py/requirements.txt not found."
        exit 1
    fi

    info "Backend venv created and dependencies installed"
}

# --- Frontend dependency check -----------------------------------------------

ensure_frontend() {
    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        info "Frontend node_modules ready"
        return
    fi

    if ! command -v node &> /dev/null; then
        echo "Error: node not found. Install Node 20+ first."
        exit 1
    fi

    warn "Frontend node_modules not found -- installing..."

    (cd "$FRONTEND_DIR" && npm ci --silent)

    info "Frontend dependencies installed"
}

# --- Data directories -------------------------------------------------------

ensure_dirs() {
    mkdir -p "$PROJECT_ROOT/data"/{listings,profiles,cache,results,applications,settings,metrics,experiments,logs,outputs}
}

# --- Service launchers -------------------------------------------------------

start_api() {
    echo "Starting backend API (port 8000)..."
    cd "$BACKEND_DIR"
    PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.api.main:app \
        --host 0.0.0.0 --port 8000 --reload
}

start_frontend() {
    echo "Starting Next.js dev server (port 3000)..."
    cd "$FRONTEND_DIR"
    npm run dev -- --port 3000
}

start_both() {
    echo "Starting backend API + Next.js frontend..."
    (trap 'kill 0' SIGINT; start_api & start_frontend; wait)
}

# --- Main --------------------------------------------------------------------

MODE="${1:-both}"

case "$MODE" in
    api|backend)
        ensure_backend
        ensure_dirs
        start_api
        ;;
    frontend)
        ensure_frontend
        start_frontend
        ;;
    both|"")
        ensure_backend
        ensure_frontend
        ensure_dirs
        start_both
        ;;
    *)
        echo "Usage: $0 [api|frontend|both]"
        exit 1
        ;;
esac
