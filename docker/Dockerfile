# Job Raider - Dockerfile for Cloud Deployment
#
# Backend API image. Local LLM calls go to the shared Ollama service
# (compose OLLAMA_HOST=ollama:11434). Do not install Ollama in this image.
#
# Author: Job Raider
# Date: 2026-04-22
#
# Usage:
#   docker build -t job-raider:latest .
#   docker run -v ./apps/backend-py/data:/app/backend-py/data --gpus all job-raider:latest
#

# Base image with CUDA support for GPU-backed Python deps (e.g. torch)
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Overridden by compose to reach Ollama on the Docker host.
ENV OLLAMA_HOST=host.docker.internal:11434

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
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

# Set working directory to match the new monorepo layout
WORKDIR /app/backend-py

# Copy only requirements first so the dependency layer stays cached
# across application code changes (source is copied last, below).
COPY apps/backend-py/requirements.txt .

# Create virtual environment inside the backend directory and install dependencies
RUN python3.11 -m venv .venv
ENV PATH="/app/backend-py/.venv/bin:$PATH"

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user for security (owns everything copied so far)
RUN useradd -m -u 1000 jobraider && \
    chown -R jobraider:jobraider /app

# Copy and set up entrypoint script (as root)
COPY docker/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy application source LAST so editing code does not invalidate the
# dependency layers above, keeping code-only rebuilds fast.
COPY --chown=jobraider:jobraider apps/backend-py/config/ ./config/
COPY --chown=jobraider:jobraider apps/backend-py/src/ ./src/
COPY --chown=jobraider:jobraider apps/backend-py/main.py .
COPY --chown=jobraider:jobraider VERSION /app/VERSION

# Switch to jobraider user for runtime
USER jobraider

# Create data directories (as jobraider user)
RUN mkdir -p /app/backend-py/data/listings \
    /app/backend-py/data/cache \
    /app/backend-py/data/results \
    /app/backend-py/data/applications \
    /app/backend-py/data/metrics \
    /app/backend-py/data/profiles \
    /app/backend-py/data/experiments \
    /app/backend-py/data/logs \
    /app/backend-py/data/outputs

# Set environment variables for the application
ENV PYTHONPATH=/app/backend-py
ENV DATA_DIR=/app/backend-py/data
ENV RESULTS_DIR=/app/backend-py/data/results

# Expose API port (Ollama listens on the shared ollama container, not here)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Set entrypoint to install Playwright browsers at runtime if needed
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Number of uvicorn workers. Profile state is backed by JSON files on the
# mounted data volume (data/profiles/), so every worker observes the same
# active profile. Override with -e UVICORN_WORKERS=<n> if needed.
ENV UVICORN_WORKERS=2

# Default command - run API server.
# Shell form so ${UVICORN_WORKERS} expands; `exec` keeps uvicorn as PID 1
# for proper signal handling.
CMD ["sh", "-c", "exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]

# Alternative commands:
# - Run pipeline once: python main.py --resume data/resume.pdf --keywords "python" --locations "remote"
# - Run CLI: python main.py --help
# - Interactive mode: python main.py --interactive
