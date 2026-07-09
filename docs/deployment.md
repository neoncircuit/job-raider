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