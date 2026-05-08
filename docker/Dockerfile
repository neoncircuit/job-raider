# Job Raider - Dockerfile for Cloud Deployment
#
# This Dockerfile sets up Job Raider for automated job application
# pipeline execution with Ollama for local model inference.
#
# Author: Job Raider
# Date: 2026-04-22
#
# Usage:
#   docker build -t job-raider:latest .
#   docker run -v ./data:/app/data --gpus all job-raider:latest
#

# Base image with CUDA support for GPU inference
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV OLLAMA_HOST=0.0.0.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    curl \
    git \
    wget \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend-py directory structure
COPY backend-py/requirements.txt .
COPY backend-py/config/ ./config/
COPY backend-py/src/ ./src/
COPY backend-py/main.py .

# Create virtual environment and install dependencies
RUN python3.10 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Ollama (requires root)
RUN curl -fsSL https://ollama.com/install.sh | sh

# Create non-root user for security
RUN useradd -m -u 1000 jobraider && \
    chown -R jobraider:jobraider /app

# Copy and set up entrypoint script (as root)
COPY docker/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to jobraider user for runtime
USER jobraider

# Create data directories (as jobraider user)
RUN mkdir -p /app/data/listings \
    /app/data/cache \
    /app/data/results \
    /app/data/applications \
    /app/data/metrics \
    /app/data/profiles \
    /app/data/experiments \
    /app/data/logs \
    /app/data/outputs

# Set environment variables for the application
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV RESULTS_DIR=/app/data/results

# Expose API port
EXPOSE 8000

# Expose Ollama port (if needed for external access)
EXPOSE 11434

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set entrypoint to install Playwright browsers at runtime if needed
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command - run API server
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# Alternative commands:
# - Run pipeline once: python main.py --resume data/resume.pdf --keywords "python" --locations "remote"
# - Run CLI: python main.py --help
# - Interactive mode: python main.py --interactive
