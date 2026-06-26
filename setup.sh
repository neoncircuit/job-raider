#!/bin/bash
# Job Raider - Setup Script
# Auto-activates .venv and installs/updates dependencies

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend-py"
VENV_DIR="$BACKEND_DIR/.venv"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    Job Raider - Setup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Track check results for summary
CHECK_RESULTS=()

# Record a check result for the summary
record_check() {
    local status="$1"
    local label="$2"
    CHECK_RESULTS+=("$status|$label")
}

# Check if git is installed
check_git() {
    print_status "Checking git..."
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        print_status "git $GIT_VERSION found [OK]"
        record_check "PASS" "git"
    else
        print_warning "git not found. Install with: sudo apt-get install -y git"
        record_check "FAIL" "git"
    fi
}

# Check if make is installed
check_make() {
    print_status "Checking make..."
    if command -v make &> /dev/null; then
        print_status "make found [OK]"
        record_check "PASS" "make"
    else
        print_warning "make not found. Install with: sudo apt-get install -y build-essential"
        print_warning "Commands like 'make dev' will not work without make."
        record_check "FAIL" "make"
    fi
}

# Check if Docker is installed and running (hard requirement)
check_docker() {
    print_status "Checking Docker..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        echo ""
        echo "Install Docker for your platform:"
        echo "  WSL2/Windows: https://docs.docker.com/desktop/setup/install/windows-install/"
        echo "  Linux:        curl -fsSL https://get.docker.com | sh"
        echo "  Then add your user: sudo usermod -aG docker \$USER"
        echo ""
        record_check "FAIL" "Docker"
        exit 1
    fi

    DOCKER_VERSION=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
    print_status "Docker $DOCKER_VERSION found [OK]"

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running!"
        echo ""
        echo "  WSL2/Windows: Start Docker Desktop from the Start menu"
        echo "  Linux:        sudo systemctl start docker"
        echo ""
        record_check "FAIL" "Docker daemon"
        exit 1
    fi
    print_status "Docker daemon is running [OK]"

    # Check Docker Compose v2
    if ! docker compose version &> /dev/null; then
        print_warning "Docker Compose v2 not found. Install via Docker Desktop or:"
        print_warning "  sudo apt-get install -y docker-compose-plugin"
        record_check "FAIL" "Docker Compose"
    else
        COMPOSE_VERSION=$(docker compose version --short 2>/dev/null)
        print_status "Docker Compose $COMPOSE_VERSION found [OK]"
        record_check "PASS" "Docker Compose"
    fi

    record_check "PASS" "Docker"
}

# Check NVIDIA GPU and Container Toolkit
check_gpu() {
    print_status "Checking GPU support..."
    if ! command -v nvidia-smi &> /dev/null; then
        print_warning "nvidia-smi not found - no NVIDIA GPU drivers installed"
        print_warning "Ollama will fall back to CPU-only mode (slower inference)"
        record_check "WARN" "NVIDIA GPU (CPU fallback)"
        return
    fi

    # Check if nvidia-smi actually works (driver loaded)
    if ! nvidia-smi &> /dev/null; then
        print_warning "nvidia-smi found but failed to run - driver issue?"
        print_warning "Check with: nvidia-smi"
        record_check "WARN" "NVIDIA GPU (driver error)"
        return
    fi

    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')
    print_status "NVIDIA GPU: $GPU_NAME ($GPU_VRAM) [OK]"

    # Check NVIDIA Container Toolkit
    if docker info 2>/dev/null | grep -q "nvidia"; then
        print_status "NVIDIA Container Toolkit configured [OK]"
        record_check "PASS" "NVIDIA GPU + Toolkit"
    else
        print_warning "NVIDIA Container Toolkit not configured"
        print_warning "GPU passthrough to Docker containers will not work."
        echo ""
        echo "  Install:  sudo apt-get install -y nvidia-container-toolkit"
        echo "  Configure: sudo nvidia-ctk runtime configure --runtime=docker"
        echo "  Restart:   Restart Docker Desktop (WSL2) or sudo systemctl restart docker (Linux)"
        echo "  Verify:    docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi"
        echo ""
        record_check "WARN" "NVIDIA GPU (toolkit missing)"
    fi
}

# Check Node.js version (v20+ required for Next.js frontend)
check_node() {
    print_status "Checking Node.js..."
    if ! command -v node &> /dev/null; then
        print_warning "Node.js not found. The Next.js frontend requires Node.js 20+."
        print_warning "Install via: https://nodejs.org/ or nvm (https://github.com/nvm-sh/nvm)"
        print_warning "Frontend setup will be skipped."
        record_check "FAIL" "Node.js"
        return
    fi

    NODE_VERSION=$(node --version | cut -c2- | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 20 ] 2>/dev/null; then
        print_warning "Node.js $(node --version) found but v20+ is required for Next.js."
        print_warning "Upgrade via: nvm install 20"
        print_warning "Frontend setup will be skipped."
        record_check "FAIL" "Node.js (version too old)"
        return
    fi

    print_status "Node.js $(node --version) found [OK]"
    record_check "PASS" "Node.js"
}

# Check if shared-services Docker network exists
check_shared_network() {
    print_status "Checking shared Docker network..."
    if docker network inspect shared-services &> /dev/null; then
        print_status "shared-services network exists [OK]"
        record_check "PASS" "shared-services network"
    else
        print_warning "shared-services Docker network not found."
        print_status "Creating shared-services network..."
        if docker network create shared-services &> /dev/null; then
            print_status "shared-services network created [OK]"
            record_check "PASS" "shared-services network (created)"
        else
            print_warning "Failed to create network. Create manually: docker network create shared-services"
            record_check "FAIL" "shared-services network"
        fi
    fi
}

# Check if shared MLflow service is configured
check_shared_mlflow() {
    print_status "Checking shared MLflow service..."
    if [ -f "$HOME/docker-services/docker-compose.yml" ]; then
        print_status "Shared MLflow config found at ~/docker-services/ [OK]"
        record_check "PASS" "Shared MLflow"
    else
        print_warning "Shared MLflow service not configured."
        print_warning "See docs/mlflow-setup.md for one-time setup instructions."
        print_warning "MLflow experiment tracking will be unavailable until configured."
        record_check "WARN" "Shared MLflow (not configured)"
    fi
}

# Check if required ports are available
check_ports() {
    print_status "Checking port availability..."

    local PORTS=("8000:Backend API" "3000:Frontend (Next.js)" "11434:Ollama" "5000:MLflow")
    local ALL_FREE=true

    for ENTRY in "${PORTS[@]}"; do
        local PORT="${ENTRY%%:*}"
        local LABEL="${ENTRY#*:}"

        # Check if port is in use (Linux/WSL)
        if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
            local PROCESS=$(ss -tlnp 2>/dev/null | grep ":${PORT} " | head -1 | grep -oP 'users:\("\K[^"]+' || echo "unknown")
            print_warning "Port $PORT ($LABEL) is in use by: $PROCESS"
            ALL_FREE=false
        elif lsof -i ":${PORT}" &> /dev/null 2>&1; then
            print_warning "Port $PORT ($LABEL) is already in use"
            ALL_FREE=false
        fi
    done

    if [ "$ALL_FREE" = true ]; then
        print_status "All required ports are available [OK]"
        record_check "PASS" "Ports"
    else
        print_warning "Some ports are occupied. Stop conflicting services or set custom ports via .env"
        record_check "WARN" "Ports (some occupied)"
    fi
}

# Check disk space for Docker and project requirements
check_disk_space() {
    print_status "Checking available disk space..."

    # Check C: drive (Windows + Docker location) - only if running in WSL
    if [ -d /mnt/c ]; then
        C_AVAILABLE=$(df /mnt/c 2>/dev/null | tail -1 | awk '{print $4}')
        if [ -n "$C_AVAILABLE" ]; then
            C_AVAILABLE_GB=$(echo "$C_AVAILABLE" | awk '{printf "%.0f", $1/1024/1024}')

            if [ "$C_AVAILABLE_GB" -lt 200 ]; then
                print_warning "Less than 200GB available on C: drive (currently ${C_AVAILABLE_GB}GB)"
                print_warning "Docker Desktop + WSL2 requires ~100GB+ for this project"
                print_warning "See docs/docker-storage.md for solutions"
            else
                print_status "C: drive has ${C_AVAILABLE_GB}GB available [OK]"
            fi
        fi
    else
        print_status "Not running in WSL - skipping C: drive check"
    fi

    # Check current drive (project location)
    CURRENT_AVAILABLE=$(df . | tail -1 | awk '{print $4}')
    CURRENT_AVAILABLE_GB=$(echo "$CURRENT_AVAILABLE" | awk '{printf "%.0f", $1/1024/1024}')

    if [ "$CURRENT_AVAILABLE_GB" -lt 50 ]; then
        print_warning "Less than 50GB available on current drive (currently ${CURRENT_AVAILABLE_GB}GB)"
        print_warning "Project data requires 20-50GB for development"
    else
        print_status "Current drive has ${CURRENT_AVAILABLE_GB}GB available [OK]"
    fi
}

# Check if Python 3.11+ is installed
check_python() {
    print_status "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed!"
        echo "Please install Python 3.11 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.11"

    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "Python $PYTHON_VERSION is installed, but Python 3.11+ is required!"
        exit 1
    fi

    print_status "Python $PYTHON_VERSION found [OK]"
}

# Create virtual environment if it doesn't exist
create_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_status "Creating virtual environment at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
        print_status "Virtual environment created [OK]"
    else
        print_status "Virtual environment already exists [OK]"
    fi
}

# Activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    # Source the activate script
    source "$VENV_DIR/bin/activate"
    print_status "Virtual environment activated [OK]"
}

# Upgrade pip
upgrade_pip() {
    print_status "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    print_status "pip upgraded [OK]"
}

# Install dependencies
install_dependencies() {
    if [ -f "$REQUIREMENTS" ]; then
        print_status "Installing dependencies from requirements.txt..."
        pip install -r "$REQUIREMENTS"
        print_status "Dependencies installed [OK]"
    else
        print_warning "requirements.txt not found, skipping dependency installation."
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating project directories..."

    # Shared data directory (bind-mounted into Docker at /app/data)
    mkdir -p "$PROJECT_ROOT/data/listings"
    mkdir -p "$PROJECT_ROOT/data/profiles"
    mkdir -p "$PROJECT_ROOT/data/cache"
    mkdir -p "$PROJECT_ROOT/data/results"
    mkdir -p "$PROJECT_ROOT/data/results/resumes"
    mkdir -p "$PROJECT_ROOT/data/results/applications"
    mkdir -p "$PROJECT_ROOT/data/applications"
    mkdir -p "$PROJECT_ROOT/data/applied_jobs"
    mkdir -p "$PROJECT_ROOT/data/assessments"
    mkdir -p "$PROJECT_ROOT/data/settings"
    mkdir -p "$PROJECT_ROOT/data/metrics"
    mkdir -p "$PROJECT_ROOT/data/experiments"
    mkdir -p "$PROJECT_ROOT/data/logs"
    mkdir -p "$PROJECT_ROOT/data/outputs"
    mkdir -p "$PROJECT_ROOT/data/chroma"
    mkdir -p "$PROJECT_ROOT/data/disc_results"
    mkdir -p "$PROJECT_ROOT/data/screenshots"
    mkdir -p "$PROJECT_ROOT/data/linkedin_session"
    mkdir -p "$PROJECT_ROOT/data/alerts"
    mkdir -p "$PROJECT_ROOT/data/reports"

    # Backend-specific directories (not Docker-mounted)
    mkdir -p "$BACKEND_DIR/notebooks"
    mkdir -p "$BACKEND_DIR/tests"

    print_status "Directories created [OK]"
}

# Set up pre-commit hook for auto-activation
setup_auto_activation() {
    print_status "Setting up auto-activation hook..."

    HOOK_FILE="$PROJECT_ROOT/.git/hooks/post-checkout"
    HOOK_SCRIPT="#!/bin/bash\n# Auto-activate venv when entering project\ncd \"$(pwd)\"\nif [ -f backend-py/.venv/bin/activate ]; then\n    source backend-py/.venv/bin/activate\nfi"

    # Only create hook if .git directory exists
    if [ -d "$PROJECT_ROOT/.git" ]; then
        echo -e "$HOOK_SCRIPT" > "$HOOK_FILE" 2>/dev/null || true
        chmod +x "$HOOK_FILE" 2>/dev/null || true
        print_status "Auto-activation hook set up [OK]"
    fi
}

# Check for required environment variables
check_env() {
    print_status "Checking environment configuration..."

    ENV_FILE="$BACKEND_DIR/.env"
    ENV_EXAMPLE="$BACKEND_DIR/.env.example"

    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            print_warning "backend-py/.env not found. Creating from .env.example..."
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            print_warning "Please edit backend-py/.env with your API keys."
        else
            print_warning "backend-py/.env.example not found. Creating empty .env..."
            touch "$ENV_FILE"
        fi
    else
        print_status ".env file exists [OK]"
    fi

    # Frontend environment
    FRONTEND_ENV_FILE="$PROJECT_ROOT/frontend-ts/.env.local"
    FRONTEND_ENV_EXAMPLE="$PROJECT_ROOT/frontend-ts/.env.example"

    if [ ! -f "$FRONTEND_ENV_FILE" ]; then
        if [ -f "$FRONTEND_ENV_EXAMPLE" ]; then
            print_warning "frontend-ts/.env.local not found. Creating from .env.example..."
            cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV_FILE"
            print_warning "Please edit frontend-ts/.env.local with your API_KEY and BACKEND_API_URL."
        else
            print_warning "frontend-ts/.env.example not found. Creating empty .env.local..."
            touch "$FRONTEND_ENV_FILE"
        fi
    else
        print_status "Frontend .env.local file exists [OK]"
    fi
}

# Set up Next.js frontend (called after check_node)
setup_frontend() {
    FRONTEND_DIR="$PROJECT_ROOT/frontend-ts"

    # Skip if Node.js check failed
    if ! command -v node &> /dev/null; then
        return
    fi
    NODE_VERSION=$(node --version | cut -c2- | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 20 ] 2>/dev/null; then
        return
    fi

    print_status "Setting up Next.js frontend..."

    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        print_status "Frontend node_modules already exists [OK]"
    else
        print_status "Installing frontend Node dependencies (npm ci)..."
        cd "$FRONTEND_DIR" && npm ci --silent
        cd "$PROJECT_ROOT"
        print_status "Frontend dependencies installed [OK]"
    fi

    print_status "Frontend setup complete [OK]"
}

# Install Playwright browsers if needed
install_playwright() {
    print_status "Checking Playwright browsers..."

    if command -v playwright &> /dev/null; then
        print_status "Installing Playwright browsers (this may take a while)..."
        playwright install chromium
        print_status "Playwright browsers installed [OK]"
    fi
}

# Pull embedding model for RAG
pull_embedding_model() {
    print_status "Checking embedding model for RAG pipeline..."

    if command -v ollama &> /dev/null; then
        if ! ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
            print_status "Pulling nomic-embed-text embedding model (~274MB)..."
            ollama pull nomic-embed-text
            print_status "Embedding model installed [OK]"
        else
            print_status "Embedding model already available [OK]"
        fi
    else
        print_status "Ollama not found locally - embedding model will be pulled at Docker runtime [SKIP]"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}    Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # Show check results
    echo -e "${BLUE}System Check Results:${NC}"
    HAS_FAILURES=false
    for ENTRY in "${CHECK_RESULTS[@]}"; do
        STATUS="${ENTRY%%|*}"
        LABEL="${ENTRY#*|}"
        if [ "$STATUS" = "PASS" ]; then
            echo -e "  ${GREEN}[PASS]${NC} $LABEL"
        elif [ "$STATUS" = "WARN" ]; then
            echo -e "  ${YELLOW}[WARN]${NC} $LABEL"
        else
            echo -e "  ${RED}[FAIL]${NC} $LABEL"
            HAS_FAILURES=true
        fi
    done
    echo ""

    if [ "$HAS_FAILURES" = true ]; then
        echo -e "${YELLOW}Some checks failed. See warnings above for fix instructions.${NC}"
        echo ""
    fi

    echo -e "To activate the virtual environment, run:"
    echo -e "${BLUE}source backend-py/.venv/bin/activate${NC}"
    echo ""
    echo -e "Next steps:"
    echo "  1. Edit backend-py/.env with your API keys (ANTHROPIC_API_KEY, RAPIDAPI_KEY)"
    echo "  2. Configure settings via web UI (Settings page) or backend-py/config/*.yaml"
    echo "  3. Run: make dev-api          (backend on :8000)"
    echo "  4. Run: make dev-frontend     (Next.js on :3000)"
    echo "  5. Or:  make dev              (both together)"
    echo "  6. Docker: docker compose up -d"
    echo ""
    echo -e "Disk space warning:"
    echo "  - Docker Desktop stores ALL data on C: drive (see docs/docker-storage.md)"
    echo "  - Requirements: 200GB+ on C:, 100GB+ on project drive"
    echo ""
    echo -e "Docker development tips:"
    echo "  - Use './docker-rebuild.sh' after code changes (NOT 'docker compose restart')"
    echo "  - This prevents WSL2 DrvFs caching issues that cause stale code in containers"
    echo ""
    echo -e "Phase 36 Features (2026-06-07):"
    echo "  - Theme Toggle: Light/dark mode switching via sidebar button"
    echo "  - Odysseus Design: Fira Code font, red accents, sharp borders"
    echo "  - Fresh Grad Mode: Projects 35%, Skills 30%, Education 20% (vs 40% exp)"
    echo "  - DISC Assessment: Most/Least forced-choice format with job matching"
    echo "  - Location Filtering: Post-filter to ensure API accuracy"
    echo "  - Documentation: See docs/fresh-grad-profile-guide.md for tips"
    echo ""
    echo -e "Phase 38 Features (2026-06-08):"
    echo "  - Test Infrastructure: Vitest for unit tests, Playwright for E2E"
    echo "  - MSW API Mocking: Realistic API responses for isolated testing"
    echo "  - Test Utilities: Common helpers reduce test code duplication"
    echo "  - Run tests: npm run test (unit), npm run test:e2e (E2E)"
    echo ""
    echo -e "Phase 41 Features (2026-06-16):"
    echo "  - Multi-Agent System: AgentCoordinator + communication bus + CareerCoachAgent"
    echo "  - 9 /api/agents/* endpoints (career analysis, gap analysis, roadmaps, goals)"
    echo "  - Non-fatal startup init; agent endpoints return 503 until the coordinator is ready"
    echo "  - Config: backend-py/config/agent_config.yaml"
    echo ""
    echo -e "Phase 42 Features (2026-06-25):"
    echo "  - LinkedIn Profile Analyzer: POST /api/profile/analyze-linkedin"
    echo "  - Models: LinkedInProfileInput, LinkedInProfileAnalysis, ProfileSectionScore, InboundAttractionInsight"
    echo "  - Frontend page: /linkedin-analysis with raw-text and structured-form tabs"
    echo "  - Unit tests: backend-py/tests/unit/test_linkedin_analyzer.py (24 tests)"
    echo ""
    echo -e "Phase 43 Features (2026-06-26):"
    echo "  - Frontend ESLint zero-warnings cleanup across all dashboard pages"
    echo "  - React Hook Form useWatch migration to avoid re-renders"
    echo "  - Stable frontend lint/type-check gates"
    echo ""
    echo -e "Phase 44 Features (2026-06-27):"
    echo "  - Robust LLM JSON extraction: markdown fence stripping + brace balancing"
    echo "  - Async singleton LinkedIn analyzer via _get_linkedin_analyzer()"
    echo "  - Restored Jobs-page ExperienceSelector filter wiring"
    echo "  - Updated documentation, tasks/todo.md, tasks/lessons.md, and setup.sh"
    echo ""
}

# Main execution
main() {
    # System prerequisites
    check_disk_space
    check_git
    check_python
    check_node
    check_make
    check_docker
    check_gpu
    check_shared_network
    check_shared_mlflow
    check_ports

    # Python environment
    create_venv
    activate_venv
    upgrade_pip
    install_dependencies

    # Project structure
    create_directories
    setup_auto_activation
    check_env

    # Tools and frontend
    install_playwright
    pull_embedding_model
    setup_frontend

    # Results
    print_summary
}

# Run main function
main
