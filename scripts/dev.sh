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
#   ./scripts/dev.sh api          # Backend only (port 8000, or the next free one)
#   ./scripts/dev.sh frontend     # Frontend only (port 3000, or the next free one)
#   ./scripts/dev.sh deps         # Only check and repair the dependencies
#   ./scripts/dev.sh app          # Lean run: production frontend, backend without reload
#
# Ports: when 8000 or 3000 is in use (for example by another project), the
# service starts on the next free port, up to DEV_PORT_SPAN (10) above. Set
# BACKEND_PORT or FRONTEND_PORT to use a fixed port without a search, and
# BACKEND_PORT_START or FRONTEND_PORT_START to search from another port.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-py"
FRONTEND_DIR="$PROJECT_ROOT/apps/frontend-ts"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python3"
# Python: the version in .python-version or newer (find_python, python_install_help)
# shellcheck source=scripts/find_python.sh
source "$PROJECT_ROOT/scripts/find_python.sh"

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

# --- Ports -------------------------------------------------------------------

# How many ports above the start port the search tries.
DEV_PORT_SPAN="${DEV_PORT_SPAN:-10}"

# Return 0 when a program listens on 127.0.0.1:$1 (bash /dev/tcp, no tools).
port_in_use() {
    (exec 3<> "/dev/tcp/127.0.0.1/$1") 2> /dev/null
}

# Print the first free port from $1 to $1 + DEV_PORT_SPAN. Return 1 when none.
pick_free_port() {
    local start="$1" port
    for ((port = start; port <= start + DEV_PORT_SPAN; port++)); do
        if ! port_in_use "$port"; then
            echo "$port"
            return 0
        fi
    done
    return 1
}

# Export a port variable unless the user set it: the start port, or the next
# free one. Stop with a message when the whole range is in use.
# Args: $1 = variable name (BACKEND_PORT or FRONTEND_PORT), $2 = start port,
#       $3 = service name for the messages.
choose_port() {
    local var="$1" start="$2" label="$3" port
    if [ -n "${!var:-}" ]; then
        export "${var?}"
        return 0
    fi
    if ! port="$(pick_free_port "$start")"; then
        echo "Error: No free port for the $label from $start to $((start + DEV_PORT_SPAN))."
        echo "Stop the program that uses these ports, or set $var to a free port."
        exit 1
    fi
    if [ "$port" != "$start" ]; then
        warn "Port $start is in use; the $label uses $port."
    fi
    export "$var=$port"
}

# --- Backend dependency check -----------------------------------------------

BACKEND_STAMP="$BACKEND_DIR/.venv/.job-raider-requirements.sha256"

# Make the backend .venv usable and up to date with its requirements.
#
# - The .venv is created when it is missing, and created again when its Python
#   does not run (for example after the base Python moved), when its Python is
#   older than .python-version, or when the core packages do not import (a
#   broken or half-finished install). A new .venv uses the newest suitable
#   Python (scripts/find_python.sh), not only the default python3, and when
#   there is none, a Python installed in .tools (ensure_python).
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
    elif [ -x "$VENV_PYTHON" ] && ! python_meets "$VENV_PYTHON" "$(python_required_version "$PROJECT_ROOT")"; then
        warn "Backend .venv uses an older Python than .python-version -- creating it again..."
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
        local python_bin
        if ! python_bin="$(ensure_python "$PROJECT_ROOT")"; then
            echo "Error: no suitable Python found."
            python_install_help "$PROJECT_ROOT"
            exit 1
        fi
        warn "Creating the backend .venv with $("$python_bin" --version)..."
        "$python_bin" -m venv "$BACKEND_DIR/.venv"
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
    choose_port BACKEND_PORT "${BACKEND_PORT_START:-8000}" backend
    echo "Starting backend API on 127.0.0.1:$BACKEND_PORT..."
    cd "$BACKEND_DIR"
    # Load apps/backend-py/.env (API_KEY, AUTH_DISABLED, provider keys), as
    # Compose does with env_file. The app itself does not read .env, and
    # variables already set in the shell take precedence.
    # Reload watches only the code and the config. Watching the whole backend
    # folder includes data/, where folders that a container wrote as root
    # (for example a browser session) stop the watcher with "Permission
    # denied", and data writes would restart the server.
    # APP_MODE=1 (make app): no auto-reload, so no file watcher and less
    # memory and CPU. make dev keeps the reload.
    local reload_args=(--reload --reload-dir "$BACKEND_DIR/src" --reload-dir "$BACKEND_DIR/config")
    if [ -n "${APP_MODE:-}" ]; then
        reload_args=()
    fi
    PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.api.main:app \
        --host 127.0.0.1 --port "$BACKEND_PORT" "${reload_args[@]}" \
        --env-file "$BACKEND_DIR/.env"
}

# The backend port that the last production build was made for. The
# WebSocket address (NEXT_PUBLIC_WS_URL) is fixed into the build. A build
# without this stamp was made for the old fixed port, 8000.
BUILD_PORT_STAMP="$FRONTEND_DIR/.next/job-raider-backend-port"

# True when the production build is missing, older than the frontend source,
# or made for another backend port.
frontend_build_needed() {
    [ ! -f "$FRONTEND_DIR/.next/BUILD_ID" ] && return 0
    [ "$(cat "$BUILD_PORT_STAMP" 2> /dev/null || echo 8000)" != "${BACKEND_PORT:-8000}" ] && return 0
    [ -n "$(find "$FRONTEND_DIR/src" "$FRONTEND_DIR/public" "$FRONTEND_DIR/package.json" \
        "$FRONTEND_DIR"/next.config.* -newer "$FRONTEND_DIR/.next/BUILD_ID" -print -quit 2> /dev/null)" ]
}

start_frontend() {
    choose_port FRONTEND_PORT "${FRONTEND_PORT_START:-3000}" frontend
    # The proxy (BACKEND_API_URL) and the pipeline progress WebSocket
    # (NEXT_PUBLIC_WS_URL) follow the backend port, unless the user set them.
    local backend_port="${BACKEND_PORT:-8000}"
    export BACKEND_API_URL="${BACKEND_API_URL:-http://127.0.0.1:$backend_port}"
    export NEXT_PUBLIC_WS_URL="${NEXT_PUBLIC_WS_URL:-ws://127.0.0.1:$backend_port}"
    cd "$FRONTEND_DIR"
    if [ -n "${APP_MODE:-}" ]; then
        # Production server: much less memory than the dev server. Build only
        # when the source or the backend port changed since the last build.
        if frontend_build_needed; then
            echo "Building the Next.js frontend (production)..."
            npm run build
            mkdir -p "$(dirname "$BUILD_PORT_STAMP")"
            echo "$backend_port" > "$BUILD_PORT_STAMP"
        fi
        echo "Starting Next.js production server on 127.0.0.1:$FRONTEND_PORT..."
        npm run start -- --hostname 127.0.0.1 --port "$FRONTEND_PORT"
        return
    fi
    echo "Starting Next.js dev server on 127.0.0.1:$FRONTEND_PORT..."
    # Bind to loopback only so other LAN devices cannot use the proxy
    # (the proxy adds X-API-Key to every forwarded request).
    npm run dev -- --hostname 127.0.0.1 --port "$FRONTEND_PORT"
}

# Start both services. In an interactive terminal with mprocs installed (a
# frontend dev dependency), show them in one split view: a process list with
# status, and the selected process's output. Set DEV_PLAIN=1, or run without
# a terminal, for the plain mixed output.
start_both() {
    local config="${1:-mprocs.yaml}"
    # Choose both ports once, here, so the two processes agree on them.
    choose_port BACKEND_PORT "${BACKEND_PORT_START:-8000}" backend
    choose_port FRONTEND_PORT "${FRONTEND_PORT_START:-3000}" frontend
    info "Frontend: http://localhost:$FRONTEND_PORT   Backend: http://127.0.0.1:$BACKEND_PORT"
    MPROCS_BIN="$FRONTEND_DIR/node_modules/.bin/mprocs"
    if [ -t 1 ] && [ -x "$MPROCS_BIN" ] && [ -z "${DEV_PLAIN:-}" ]; then
        echo "Starting backend API + Next.js frontend in mprocs (q quits)..."
        cd "$PROJECT_ROOT"
        # The checks ran above; the two processes do not repeat them.
        export DEV_DEPS_CHECKED=1
        exec "$MPROCS_BIN" --config "$PROJECT_ROOT/$config"
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
    app)
        ensure_backend
        ensure_frontend
        ensure_dirs
        export APP_MODE=1
        start_both mprocs.app.yaml
        ;;
    app-api)
        ensure_backend
        ensure_dirs
        APP_MODE=1 start_api
        ;;
    app-frontend)
        ensure_frontend
        APP_MODE=1 start_frontend
        ;;
    *)
        echo "Usage: $0 [api|frontend|both|deps|app|app-api|app-frontend]"
        exit 1
        ;;
esac
