#!/bin/bash
# Job Raider - Development Server
# Runs API server and keeps CLI accessible

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Job Raider - Development Mode${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Function to cleanup background processes
cleanup() {
    echo -e "\n${YELLOW}Stopping development server...${NC}"
    jobs -p | xargs -r kill 2>/dev/null || true
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Check if venv exists
if [ ! -d "apps/backend-py/.venv" ]; then
    echo -e "${RED}Error: apps/backend-py/.venv not found${NC}"
    echo "Run: ./setup.sh"
    exit 1
fi

# Activate venv
source apps/backend-py/.venv/bin/activate

# Install/update dependencies
echo -e "${GREEN}Ensuring dependencies are up to date...${NC}"
cd apps/backend-py
pip install -q -r requirements.txt 2>/dev/null || {
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
}
cd ..

echo ""
echo -e "${GREEN}Starting services...${NC}"
echo ""

# Start API server in background
echo -e "${BLUE}[1/2]${NC} Starting API server on http://localhost:8000"
cd apps/backend-py
PYTHONPATH=. python -m uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > ../logs/api.log 2>&1 &
API_PID=$!
cd ..

# Wait a moment for API server to start
sleep 2

# Check if API server started successfully
if kill -0 $API_PID 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} API server running (PID: $API_PID)"
    echo -e "  ${GREEN}→${NC} Docs: http://localhost:8000/docs"
else
    echo -e "  ${RED}✗${NC} API server failed to start"
    cat logs/api.log
    exit 1
fi

echo ""
echo -e "${BLUE}[2/2]${NC} CLI ready - use 'cd apps/backend-py && python main.py' for pipeline operations"
echo ""
echo -e "${YELLOW}Services running:${NC}"
echo -e "  • API:  http://localhost:8000"
echo -e "  • Docs: http://localhost:8000/docs"
echo -e "  • CLI:  cd apps/backend-py && python main.py --help"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Monitor API server logs
tail -f logs/api.log 2>/dev/null &
TAIL_PID=$!

# Keep script running
wait $API_PID 2>/dev/null
