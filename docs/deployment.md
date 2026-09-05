# Job Raider - Deployment Configuration Guide

## Overview

Job Raider supports multiple deployment scenarios with different LLM provider configurations. This guide helps you choose and configure the right setup for your needs.

## LLM Provider Options

### Option 1: Local Ollama (Recommended for Development)

**Best for:** Development, testing, privacy-focused users

**Requirements:**
- Ollama installed locally
- 8GB+ RAM for small models (3B parameters)
- 16GB+ RAM for medium models (7B parameters)

**Configuration:**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended models
ollama pull qwen2.5:3b      # For selection/scoring
ollama pull qwen2.5:7b      # For resume writing/JD extraction
ollama pull nomic-embed-text # For embeddings

# Set environment variable
export OLLAMA_HOST=host.docker.internal:11434  # Mac/Windows
# OR for Linux: export OLLAMA_HOST=172.17.0.1:11434  # Docker bridge IP

# Start application
docker compose up -d
```

**Advantages:**
- ✅ Free (no API costs)
- ✅ Privacy (data stays local)
- ✅ Fast (no network latency)

**Limitations:**
- ❌ Requires local resources
- ❌ Model quality limited by local hardware

---

### Option 2: Docker Ollama Service

**Best for:** Production deployments, containerized environments

**Configuration:**

```yaml
# Add to docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: job-raider-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama/models
    networks:
      - job-raider-network
    restart: unless-stopped

volumes:
  ollama-models:

# Update backend environment
backend:
  environment:
    - OLLAMA_HOST=ollama:11434
```

```bash
# Start services
docker compose up -d

# Pull models in the container
docker exec job-raider-ollama ollama pull qwen2.5:3b
docker exec job-raider-ollama ollama pull qwen2.5:7b
docker exec job-raider-ollama ollama pull nomic-embed-text
```

---

### Option 3: Cloud API with Fallback

**Best for:** Production, users without local hardware

**Configuration:**

```bash
# apps/backend-py/.env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OLLAMA_HOST=ollama:11434  # Optional local Ollama
```

**API Keys Setup:**

**Anthropic Claude:**
1. Visit https://console.anthropic.com/
2. Create API key
3. Add to `apps/backend-py/.env`

**Google Gemini:**
1. Visit https://makersuite.google.com/app/apikey
2. Create API key
3. Add to `apps/backend-py/.env`

**Cost Estimation:**
- Anthropic Claude Sonnet: ~$3-15 per 1M tokens
- Google Gemini 2.5 Flash: ~$0.15-0.60 per 1M tokens
- Typical job application: ~$0.01-0.10 per application

---

## Platform-Specific Notes

### macOS/Windows

```bash
# Use host.docker.internal for local Ollama
export OLLAMA_HOST=host.docker.internal:11434
```

### Linux (Docker Desktop)

```bash
# Use host.docker.internal (Docker Desktop 20.10+)
export OLLAMA_HOST=host.docker.internal:11434
```

### Linux (Native Docker)

```bash
# Find Docker bridge IP
ip addr show docker0 | grep inet

# Use bridge IP
export OLLAMA_HOST=172.17.0.1:11434
```

---

## Troubleshooting

### Issue: "No LLM providers available"

**Symptoms:** Application starts but fails when using LLM features

**Solutions:**
1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Verify environment variable: `docker compose exec backend env | grep OLLAMA`
3. Check backend logs: `docker compose logs backend | grep -i provider`

### Issue: "Ollama connection refused"

**Symptoms:** Backend can't reach local Ollama

**Solutions:**
1. Ensure Ollama is running: `ollama list`
2. Check firewall settings
3. Verify correct host for your platform (see above)
4. Try `OLLAMA_HOST=172.17.0.1:11434` for Linux

### Issue: "Fallback unavailable"

**Symptoms:** Warning about missing API keys

**Solutions:**
1. Add Anthropic API key to `apps/backend-py/.env`
2. Add Gemini API key to `apps/backend-py/.env`
3. Or ignore if you only use local Ollama

---

## Production Recommendations

1. **Always configure fallback providers** (Anthropic/Gemini)
2. **Monitor LLM availability** at startup
3. **Set usage limits** to prevent cost overruns
4. **Use separate API keys** for development/production
5. **Implement rate limiting** for API calls

---

## Quick Start Commands

```bash
# Full setup with local Ollama (recommended)
git clone <repository>
cd job-raider
./setup.sh                    # Install dependencies
docker compose up -d          # Start services
ollama pull qwen2.5:3b       # Pull models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
curl http://localhost:3000    # Access frontend

# With cloud API fallback
echo "ANTHROPIC_API_KEY=your_key" >> apps/backend-py/.env
docker compose up -d --force-recreate

# Production deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Code-only backend overlay (Hub auth blocked)

When `docker compose build backend` fails pulling `nvidia/cuda` with a credentials error, but a prior `job-raider-backend:latest` exists locally, apply source changes without Hub:

```bash
docker tag job-raider-backend:latest job-raider-backend:pre-overlay
docker build --network=none -t job-raider-backend:latest -f docker/Dockerfile.overlay .
docker compose up -d --no-build --force-recreate backend
```

This path is temporary ops glue ([`docker/Dockerfile.overlay`](../docker/Dockerfile.overlay)). Prefer a full rebuild from [`docker/Dockerfile`](../docker/Dockerfile) once Docker Hub credentials work again.

### Version checkpoints (semver + git tags)

Product version is a single line in the repo-root [`VERSION`](../VERSION) file. The FastAPI app and `/api/version` read that file (Docker images copy it to `/app/VERSION`). Keep [`apps/frontend-ts/package.json`](../apps/frontend-ts/package.json) `"version"` equal to `VERSION` on every release. Record user-facing changes in [`CHANGELOG.md`](../CHANGELOG.md). The `0.1.0` section documents pre-Cursor foundation work plus later commits through the first tag tip; do not invent earlier tags for that history.

While on **0.x**: MINOR = feature checkpoint, PATCH = fix-only. Do not auto-bump on every commit.

Release ritual (from a clean `main` with CI green):

```bash
# 1. Move Unreleased notes into a new CHANGELOG section; set VERSION and
#    apps/frontend-ts/package.json to the same X.Y.Z
# 2. Commit the bump
git add VERSION CHANGELOG.md apps/frontend-ts/package.json
git commit -m "$(cat <<'EOF'
chore: release vX.Y.Z

EOF
)"

# 3. Annotated tag (CI may publish Docker images on v* tags)
git tag -a vX.Y.Z -m "vX.Y.Z"

# 4. Push commit and tag when ready to publish
git push origin main
git push origin vX.Y.Z
```

Verify the running API after deploy:

```bash
curl -s http://localhost:8000/api/version
```

---

## Security Considerations

1. **Never commit .env files** to version control
2. **Use separate API keys** for different environments
3. **Rotate API keys regularly** (especially if compromised)
4. **Monitor usage** for unusual patterns
5. **Implement proper logging** without exposing sensitive data

---

## Support

For issues or questions:
- Check logs: `docker compose logs -f backend`
- Health check: `curl http://localhost:8000/api/health`
- Provider status: Check startup logs for "=== LLM Provider Validation ==="