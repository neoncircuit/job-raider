#!/bin/bash
# Job Raider - Docker Run Script
# Finds available ports and starts all Docker containers.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

source scripts/find-port.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Job Raider - Docker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Backend is not published on the host (local-first). Only the frontend
# loopback port needs a free host port. Ollama (the WSL service) and the
# shared MLflow (~/docker-services) run outside this compose project on
# their own ports, so this script does not pick ports for them.
FRONTEND_PORT=$(find_port 3000)
OLLAMA_URL="http://localhost:11434"
MLFLOW_URL="http://localhost:${MLFLOW_PORT:-5000}"

echo -e "${GREEN}Services:${NC}"
echo -e "  Frontend:  ${BLUE}http://127.0.0.1:$FRONTEND_PORT${NC}"
echo -e "  Backend:   ${BLUE}Compose network only (backend:8000)${NC}"
echo -e "  MLflow:    ${BLUE}$MLFLOW_URL${NC} (shared, ~/docker-services)"
echo -e "  Ollama:    ${BLUE}$OLLAMA_URL${NC} (WSL service)"
if ! curl -sf -m 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
    echo -e "  ${YELLOW}Ollama does not answer. Start it in WSL: sudo systemctl start ollama${NC}"
fi
echo ""

export FRONTEND_PORT
unset BACKEND_PORT

# Stop existing containers
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker compose down 2>/dev/null || true

# Start (images already built; rebuild only if source changed)
echo ""
echo -e "${GREEN}Starting containers...${NC}"
docker compose up -d --build

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services running${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Dashboard:  ${BLUE}http://127.0.0.1:$FRONTEND_PORT${NC}"
echo -e "  API:        ${BLUE}via frontend proxy (backend not published)${NC}"
echo -e "  MLflow:     ${BLUE}$MLFLOW_URL${NC}"
echo ""
echo -e "${YELLOW}Logs:${NC}  docker compose logs -f"
echo -e "${YELLOW}Stop:${NC}  docker compose down"
echo ""
