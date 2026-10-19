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
# loopback port and shared services need free host ports.
OLLAMA_PORT=$(find_port 11434)
FRONTEND_PORT=$(find_port 3000)
MLFLOW_PORT=$(find_port 5000)

echo -e "${GREEN}Ports allocated:${NC}"
echo -e "  Frontend:  ${BLUE}http://127.0.0.1:$FRONTEND_PORT${NC}"
echo -e "  Backend:   ${BLUE}Compose network only (backend:8000)${NC}"
echo -e "  MLflow:    ${BLUE}http://localhost:$MLFLOW_PORT${NC}"
echo -e "  Ollama:    ${BLUE}localhost:$OLLAMA_PORT${NC}"
echo ""

export OLLAMA_PORT FRONTEND_PORT MLFLOW_PORT
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
echo -e "  MLflow:     ${BLUE}http://localhost:$MLFLOW_PORT${NC}"
echo ""
echo -e "${YELLOW}Logs:${NC}  docker compose logs -f"
echo -e "${YELLOW}Stop:${NC}  docker compose down"
echo ""
