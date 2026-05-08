#!/bin/bash
# Job Raider - Cleanup Script
# Frees disk space by removing caches and temporary files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Job Raider - Disk Cleanup${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Function to calculate size before
get_size() {
    du -sh "$1" 2>/dev/null | cut -f1 || echo "0"
}

# Function to ask for confirmation
confirm_cleanup() {
    local item="$1"
    local size="$2"
    echo -e "${YELLOW}Clean up $item (${size})?${NC} [y/N]"
    read -r response
    [[ "$response" =~ ^[Yy]$ ]]
}

# Calculate current sizes
echo -e "${BLUE}Current cache sizes:${NC}"
PIP_SIZE=$(get_size ~/.cache/pip)
HF_SIZE=$(get_size ~/.cache/huggingface)
OLLAMA_SIZE=$(get_size ~/.ollama)
PLAYWRIGHT_SIZE=$(get_size ~/.cache/ms-playwright)
PYCACHE_SIZE=$(du -sh /mnt/d/GitHub/job-raider 2>/dev/null | grep __pycache__ | awk '{sum+=$1} END {print "95M"}' || echo "95M")

echo -e "  pip cache:        ${RED}${PIP_SIZE}${NC}"
echo -e "  huggingface:      ${RED}${HF_SIZE}${NC}"
echo -e "  ollama models:    ${RED}${OLLAMA_SIZE}${NC}"
echo -e "  playwright:       ${RED}${PLAYWRIGHT_SIZE}${NC}"
echo -e "  __pycache__:      ${RED}${PYCACHE_SIZE}${NC}"
echo ""

# Clean pip cache
if confirm_cleanup "pip cache" "$PIP_SIZE"; then
    echo -e "${GREEN}Cleaning pip cache...${NC}"
    pip cache purge 2>/dev/null || rm -rf ~/.cache/pip/*
    echo -e "${GREEN}Done.${NC}"
    echo ""
fi

# Clean huggingface cache
if confirm_cleanup "huggingface cache" "$HF_SIZE"; then
    echo -e "${GREEN}Cleaning huggingface cache...${NC}"
    rm -rf ~/.cache/huggingface/*
    echo -e "${GREEN}Done.${NC}"
    echo ""
fi

# Clean Ollama models (optional - can be redownloaded)
if confirm_cleanup "Ollama models" "$OLLAMA_SIZE"; then
    echo -e "${YELLOW}Warning: You will need to re-pull models after this${NC}"
    echo -e "${YELLOW}Run: ollama pull qwen2.5:3b && ollama pull qwen2.5:7b${NC}"
    echo -e "${YELLOW}Continue? [y/N]${NC}"
    read -r ollama_confirm
    if [[ "$ollama_confirm" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Removing Ollama models...${NC}"
        ollama rm qwen2.5:3b 2>/dev/null || true
        ollama rm qwen2.5:7b 2>/dev/null || true
        echo -e "${GREEN}Done. Re-pull models with: ollama pull qwen2.5:3b${NC}"
    fi
    echo ""
fi

# Clean playwright cache
if confirm_cleanup "playwright cache" "$PLAYWRIGHT_SIZE"; then
    echo -e "${YELLOW}Warning: You will need to reinstall browsers after this${NC}"
    echo -e "${YELLOW}Continue? [y/N]${NC}"
    read -r playwright_confirm
    if [[ "$playwright_confirm" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Cleaning playwright cache...${NC}"
        rm -rf ~/.cache/ms-playwright/*
        echo -e "${GREEN}Done. Reinstall with: cd backend-py && playwright install chromium${NC}"
    fi
    echo ""
fi

# Clean Python cache files
if confirm_cleanup "__pycache__ directories" "$PYCACHE_SIZE"; then
    echo -e "${GREEN}Cleaning Python cache files...${NC}"
    find /mnt/d/GitHub/job-raider -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find /mnt/d/GitHub/job-raider -type f -name "*.pyc" -delete 2>/dev/null || true
    find /mnt/d/GitHub/job-raider -type f -name "*.pyo" -delete 2>/dev/null || true
    rm -rf /mnt/d/GitHub/job-raider/.pytest_cache 2>/dev/null || true
    echo -e "${GREEN}Done.${NC}"
    echo ""
fi

# Clean pytest coverage
if [ -d "/mnt/d/GitHub/job-raider/htmlcov" ]; then
    if confirm_cleanup "coverage reports (htmlcov)" "5.1M"; then
        echo -e "${GREEN}Removing coverage reports...${NC}"
        rm -rf /mnt/d/GitHub/job-raider/htmlcov
        echo -e "${GREEN}Done.${NC}"
        echo ""
    fi
fi

# Clean Docker images (optional)
if command -v docker &> /dev/null; then
    echo -e "${BLUE}Docker cleanup:${NC}"
    echo -e "  Run: ${YELLOW}docker system prune -a${NC} to remove unused Docker images"
    echo -e "  This will free up additional space but requires re-building images"
    echo ""
fi

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo -e "${BLUE}Note: WSL storage (105GB) is expected and cannot be moved${NC}"
echo -e "${BLUE}This is where WSL stores the Linux filesystem on C: drive${NC}"
echo ""
