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

# Check if Python 3.10+ is installed
check_python() {
    print_status "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed!"
        echo "Please install Python 3.10 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.10"

    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "Python $PYTHON_VERSION is installed, but Python 3.10+ is required!"
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
    mkdir -p "$PROJECT_ROOT/data/applications"
    mkdir -p "$PROJECT_ROOT/data/settings"
    mkdir -p "$PROJECT_ROOT/data/metrics"
    mkdir -p "$PROJECT_ROOT/data/experiments"
    mkdir -p "$PROJECT_ROOT/data/logs"
    mkdir -p "$PROJECT_ROOT/data/outputs"

    # Backend-specific directories (not Docker-mounted)
    mkdir -p "$BACKEND_DIR/data/kaggle"
    mkdir -p "$BACKEND_DIR/data/chroma"
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

# Set up Next.js frontend
setup_frontend() {
    print_status "Setting up Next.js frontend..."

    FRONTEND_DIR="$PROJECT_ROOT/frontend-ts"

    if ! command -v node &> /dev/null; then
        print_warning "Node.js not found. Install Node 20+ to run the frontend locally."
        print_warning "Skipping frontend dependency installation."
        return
    fi

    NODE_VERSION=$(node --version | cut -c2- | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 20 ] 2>/dev/null; then
        print_warning "Node.js $NODE_VERSION found but 20+ is recommended."
    else
        print_status "Node.js $(node --version) found [OK]"
    fi

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
    echo -e "${GREEN}    Setup Complete! [OK]${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "To activate the virtual environment, run:"
    echo -e "${BLUE}source backend-py/.venv/bin/activate${NC}"
    echo ""
    echo -e "Or add this to your ~/.bashrc or ~/.zshrc:"
    echo -e "${BLUE}export PATH=\"$(pwd)/backend-py/.venv/bin:\$PATH\"${NC}"
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
    echo -e "Project status (31 phases completed):"
    echo "  - Next.js + Tailwind frontend (replaces Streamlit)"
    echo "  - RAG semantic matching with ChromaDB vector store and nomic-embed-text embeddings"
    echo "  - JSearch API scraper via RapidAPI (replaces broken Indeed/Glassdoor)"
    echo "  - Applications tracker with custom statuses"
    echo "  - AI-powered resume analysis (general + job-specific gap analysis)"
    echo "  - 5 resume templates with ATS-friendly mode and section customization"
    echo "  - MLflow experiment tracking (docker compose up mlflow)"
    echo "  - Sentry error tracking (optional, disabled by default)"
    echo "  - LLM-based job classification with rich metadata (industry, role, company size, etc.)"
    echo "  - LinkedIn Easy Apply automation with form parsing, answer engine, and safety limits"
    echo "  - Job trust scoring with tiered ratings, per-category breakdowns, and LLM-enhanced analysis"
    echo ""
    echo -e "Docker development tips:"
    echo "  - Use './docker-rebuild.sh' after code changes (NOT 'docker compose restart')"
    echo "  - This prevents WSL2 DrvFs caching issues that cause stale code in containers"
    echo ""
}

# Main execution
main() {
    check_disk_space
    check_python
    create_venv
    activate_venv
    upgrade_pip
    install_dependencies
    create_directories
    setup_auto_activation
    check_env
    install_playwright
    pull_embedding_model
    setup_frontend
    print_summary
}

# Run main function
main
