#!/bin/bash
# Job Raider - Dev Launcher with Self-Healing Dependencies
#
# Pre-flight checks before the services start: the backend .venv and the
# frontend node_modules are created when missing, repaired when broken, and
# updated when requirements.txt, requirements-optional.txt, or
# package-lock.json changed since the last install.
#
# Usage:
#   ./scripts/dev.sh              # Start both backend + frontend
#   ./scripts/dev.sh api          # Backend only (port 8000)
#   ./scripts/dev.sh frontend     # Frontend only (port 3000)
#   ./scripts/dev.sh deps         # Only check and repair the dependencies

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-py"
FRONTEND_DIR="$PROJECT_ROOT/apps/frontend-ts"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python3"

# --- Helpers ----------------------------------------------------------------

info()  { echo -e "\033[0;32m[OK]\033[0m $1"; }
warn()  { echo -e "\033[1;33m[!!]\033[0m $1"; }

# Print the SHA-256 of the given files together ("none" when none exists).
files_sha256() {
    local existing=()
    for f in "$@"; do [ -f "$f" ] && existing+=("$f"); done
    if [ ${#existing[@]} -eq 0 ]; then echo none; return; fi
    cat "${existing[@]}" | sha256sum | cut -d' ' -f1
}

# --- Backend dependency check -----------------------------------------------

BACKEND_STAMP="$BACKEND_DIR/.venv/.job-raider-requirements.sha256"

# Make the backend .venv usable and up to date with its requirements.
#
# - The .venv is created when it is missing, and created again when its Python
#   does not run (for example after the base Python moved) or when the core
#   packages do not import (a broken or half-finished install).
# - pip installs the requirements again when requirements.txt or
#   requirements-optional.txt changed since the last install (a hash stamp in
#   the .venv), so a pull with new requirements needs no manual step.
# - llmfit (requirements-optional.txt) is optional: a failed install warns,
#   and NO_LLMFIT=1 skips it (as ./setup.sh --no-llmfit does).
ensure_backend() {
    [ -n "${DEV_DEPS_CHECKED:-}" ] && return 0
    local want
    want="$(files_sha256 "$BACKEND_DIR/requirements.txt" "$BACKEND_DIR/requirements-optional.txt")"

    if [ -e "$BACKEND_DIR/.venv" ] && ! "$VENV_PYTHON" -c "import sys" &> /dev/null; then
        warn "Backend .venv does not run -- creating it again..."
        rm -rf "$BACKEND_DIR/.venv"
    elif [ -x "$VENV_PYTHON" ] && ! "$VENV_PYTHON" -c "import fastapi, uvicorn, pydantic, setuptools" &> /dev/null; then
        warn "Backend .venv has broken packages -- creating it again..."
        rm -rf "$BACKEND_DIR/.venv"
    fi

    if [ -x "$VENV_PYTHON" ] && [ "$(cat "$BACKEND_STAMP" 2> /dev/null)" = "$want" ]; then
        info "Backend venv ready"
        return 0
    fi

    if [ ! -x "$VENV_PYTHON" ]; then
        if ! command -v python3 &> /dev/null; then
            echo "Error: python3 not found. Install Python 3.11+ first."
            exit 1
        fi
        warn "Creating the backend .venv..."
        python3 -m venv "$BACKEND_DIR/.venv"
    else
        warn "Backend requirements changed -- updating the .venv..."
    fi

    if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
        echo "Error: apps/backend-py/requirements.txt not found."
        exit 1
    fi
    "$VENV_PYTHON" -m pip install -q --upgrade pip setuptools wheel
    "$VENV_PYTHON" -m pip install -q -r "$BACKEND_DIR/requirements.txt"
    if [ -f "$BACKEND_DIR/requirements-optional.txt" ] && [ -z "${NO_LLMFIT:-}" ]; then
        "$VENV_PYTHON" -m pip install -q -r "$BACKEND_DIR/requirements-optional.txt" \
            || warn "llmfit could not be installed; Settings shows no hardware fit (docs/hardware-fit.md)."
    fi
    echo "$want" > "$BACKEND_STAMP"
    info "Backend venv ready (dependencies installed)"
}

# --- Frontend dependency check -----------------------------------------------

FRONTEND_STAMP="$FRONTEND_DIR/node_modules/.job-raider-lock.sha256"

# Make node_modules match package-lock.json: run npm ci when node_modules is
# missing, when the Next.js binary is missing (a broken install), or when the
# lockfile changed since the last install (a hash stamp in node_modules).
ensure_frontend() {
    [ -n "${DEV_DEPS_CHECKED:-}" ] && return 0
    local want
    want="$(files_sha256 "$FRONTEND_DIR/package-lock.json")"

    if [ -x "$FRONTEND_DIR/node_modules/.bin/next" ] \
        && [ "$(cat "$FRONTEND_STAMP" 2> /dev/null)" = "$want" ]; then
        info "Frontend node_modules ready"
        return 0
    fi

    if ! command -v node &> /dev/null; then
        echo "Error: node not found. Install the Node version in .nvmrc (24) first."
        exit 1
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        warn "Frontend node_modules not found -- installing..."
    else
        warn "Frontend node_modules is out of date or broken -- installing again..."
    fi
    (cd "$FRONTEND_DIR" && npm ci --silent --no-audit --no-fund)
    echo "$want" > "$FRONTEND_STAMP"
    info "Frontend node_modules ready (dependencies installed)"
}

# --- Data directories -------------------------------------------------------

ensure_dirs() {
    mkdir -p "$BACKEND_DIR/data"/{listings,profiles,cache,results,applications,settings,metrics,experiments,logs,outputs}
}

# --- Service launchers -------------------------------------------------------

start_api() {
    echo "Starting backend API on 127.0.0.1:8000..."
    cd "$BACKEND_DIR"
    # Load apps/backend-py/.env (API_KEY, AUTH_DISABLED, provider keys), as
    # Compose does with env_file. The app itself does not read .env, and
    # variables already set in the shell take precedence.
    # Reload watches only the code and the config. Watching the whole backend
    # folder includes data/, where folders that a container wrote as root
    # (for example a browser session) stop the watcher with "Permission
    # denied", and data writes would restart the server.
    PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.api.main:app \
        --host 127.0.0.1 --port 8000 --reload \
        --reload-dir "$BACKEND_DIR/src" --reload-dir "$BACKEND_DIR/config" \
        --env-file "$BACKEND_DIR/.env"
}

start_frontend() {
    echo "Starting Next.js dev server on 127.0.0.1:3000..."
    cd "$FRONTEND_DIR"
    # Bind to loopback only so other LAN devices cannot use the proxy
    # (the proxy adds X-API-Key to every forwarded request).
    npm run dev -- --hostname 127.0.0.1 --port 3000
}

# Start both services. In an interactive terminal with mprocs installed (a
# frontend dev dependency), show them in one split view: a process list with
# status, and the selected process's output. Set DEV_PLAIN=1, or run without
# a terminal, for the plain mixed output.
start_both() {
    MPROCS_BIN="$FRONTEND_DIR/node_modules/.bin/mprocs"
    if [ -t 1 ] && [ -x "$MPROCS_BIN" ] && [ -z "${DEV_PLAIN:-}" ]; then
        echo "Starting backend API + Next.js frontend in mprocs (q quits)..."
        cd "$PROJECT_ROOT"
        # The checks ran above; the two processes do not repeat them.
        export DEV_DEPS_CHECKED=1
        exec "$MPROCS_BIN" --config "$PROJECT_ROOT/mprocs.yaml"
    fi
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
    deps)
        ensure_backend
        ensure_frontend
        ensure_dirs
        ;;
    *)
        echo "Usage: $0 [api|frontend|both|deps]"
        exit 1
        ;;
esac
