# Job Raider - Disk Space Guide

This guide explains disk space usage for Job Raider and how to reclaim space when needed.

## Space Usage Breakdown

**Note:** Sizes shown below are estimates as of April 2026. Your actual usage may vary. See "Checking Actual Sizes" below for commands to check your current usage.

Typical disk space consumption on a Windows/WSL system:

| Location | Estimated Size | Description | Removable |
|----------|----------------|-------------|-----------|
| `~/.cache/pip` | ~14GB | Python package cache | Yes, safe |
| `~/.cache/huggingface` | ~12GB | ML model cache | Yes, if not used |
| `~/.ollama` | ~7.2GB | Ollama LLM models | Yes, re-pull needed |
| `~/.cache/ms-playwright` | ~1.2GB | Browser binaries | Yes, reinstall needed |
| `~/.cache/puppeteer` | ~626MB | Browser binaries | Yes |
| `__pycache__` | ~95MB | Python bytecode | Yes, auto-regenerates |
| `htmlcov` | ~5MB | Test coverage reports | Yes |
| WSL storage | ~105GB | Linux filesystem on C: | No, required |

**Note:** WSL storage on C drive is expected behavior. Even if your project is on D drive, WSL stores the Linux filesystem (including metadata and package installations) on your C drive at `%LOCALAPPDATA%\Packages\*Ubuntu*\`.

## Checking Actual Sizes

To check your actual disk usage, run these commands:

```bash
# Check all cache directories
du -sh ~/.cache/* 2>/dev/null | sort -hr

# Check specific locations
du -sh ~/.cache/pip
du -sh ~/.cache/huggingface
du -sh ~/.ollama
du -sh ~/.cache/ms-playwright
du -sh ~/.cache/puppeteer

# Check Python cache in project
find /mnt/d/GitHub/job-raider -name "__pycache__" -type d -exec du -sh {} \; 2>/dev/null | awk '{sum+=$1} END {print sum " total"}'

# Check Docker usage
docker system df

# Check overall disk space
df -h /mnt/c
```

For a comprehensive overview, run:

```bash
# Quick space check script
echo "=== Cache Directories ==="
du -sh ~/.cache/pip ~/.cache/huggingface ~/.cache/ms-playwright ~/.ollama 2>/dev/null | sort -hr

echo ""
echo "=== Project Cache ==="
find /mnt/d/GitHub/job-raider -name "__pycache__" -type d -exec du -sh {} \; 2>/dev/null | awk '{sum+=$1} END {print "Total __pycache__: " sum}'

echo ""
echo "=== Docker ==="
docker system df 2>/dev/null || echo "Docker not running"

echo ""
echo "=== WSL Storage (C Drive) ==="
du -sh /mnt/c/Users/*/AppData/Local/Packages/*Ubuntu* 2>/dev/null | head -1
```

## Important Notes

### No Training Involved

Job Raider does **not** train any models. It uses pre-trained models:
- **qwen2.5:3b** and **qwen2.5:7b** - Pre-trained by Ollama, just download and use
- No training data, no fine-tuning, no learning process

Cleaning caches will **not** require retraining anything.

### Project Files Location

Your actual project files are on D drive and do not duplicate. The space on C drive is from:
- Package caches (pip, huggingface, etc.)
- WSL Linux filesystem overhead
- Downloaded models and binaries

## Reclaiming Space

### Quick Cleanup (Safe)

```bash
# Clean pip cache (~14GB)
pip cache purge

# Clean Python bytecode (~95MB)
find /mnt/d/GitHub/job-raider -type d -name "__pycache__" -exec rm -rf {} +
find /mnt/d/GitHub/job-raider -type f -name "*.pyc" -delete
find /mnt/d/GitHub/job-raider -type f -name "*.pyo" -delete
rm -rf /mnt/d/GitHub/job-raider/.pytest_cache

# Clean coverage reports (~5MB)
rm -rf /mnt/d/GitHub/job-raider/htmlcov
```

### Medium Cleanup (Requires Reinstall)

```bash
# Clean HuggingFace cache (~12GB)
# Only if you don't use HuggingFace models
rm -rf ~/.cache/huggingface/*

# Reinstall Playwright browsers (~1.2GB)
cd backend-py
playwright install chromium
```

### Deep Cleanup (Requires Re-pull)

```bash
# Remove Ollama models (~7.2GB)
ollama rm qwen2.5:3b
ollama rm qwen2.5:7b

# Re-pull models (takes seconds to minutes)
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

### Docker Cleanup

```bash
# Remove unused Docker images and containers
docker system prune -a

# Warning: This requires re-building Docker images
# Run: docker-compose build
```

## Before Cleaning

### Check What You're Using

```bash
# View cache sizes
du -sh ~/.cache/*
du -sh ~/.ollama

# Check Docker usage
docker system df
```

### Ensure Project Still Works

After cleaning, verify your setup:

```bash
# Check Python environment
cd backend-py
python --version
pip list

# Check Ollama models
ollama list

# Test the project
python main.py --help
```

## Maintenance Schedule

Recommended cleanup frequency:

| Task | Frequency | Impact |
|------|-----------|--------|
| pip cache purge | Monthly | 14GB reclaimed |
| __pycache__ cleanup | Weekly | 95MB reclaimed |
| Docker prune | As needed | Variable |
| Ollama model removal | When not using | 7.2GB reclaimed |

## Storage Recommendations

### Minimum Requirements

- C drive: ~50GB free (for WSL and caches)
- D drive (project): ~10GB
- Additional space for scraped job data

### Optimal Setup

- C drive: ~100GB free (comfortable for development)
- D drive: ~20GB (project + data + models)
- SSD recommended for better performance

## WSL-Specific Notes

### WSL Storage Location

WSL2 stores the Linux filesystem on your C drive, regardless of where your project files are located:

```
C:\Users\<username>\AppData\Local\Packages\<WSL-DistroID>\LocalState\
```

This is approximately 105GB and cannot be moved. This is expected behavior.

### Reducing WSL Storage

To minimize WSL storage growth:

1. **Avoid installing unnecessary packages** in WSL
2. **Clean package caches regularly** (pip, apt, etc.)
3. **Use Docker for isolation** instead of installing directly in WSL
4. **Move large datasets** to your D drive mount point

### Checking WSL Size

```powershell
# In PowerShell
Get-ChildItem -Path "$env:LOCALAPPDATA\Packages" -Directory | Where-Object { $_.Name -like "*Ubuntu*" } | ForEach-Object {
    $size = (Get-ChildItem -Path $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "$($_.Name): $([math]::Round($size, 2)) GB"
}
```

## Troubleshooting

### Low Disk Space on C Drive

If C drive is full:

1. Run Windows Disk Cleanup
2. Clean pip cache: `pip cache purge`
3. Clean HuggingFace cache (if not used)
4. Remove unused Docker images: `docker system prune -a`
5. Consider removing old WSL instances (careful!)

### Ollama Models Not Found After Cleanup

```bash
# Check installed models
ollama list

# Re-pull if missing
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

### Project Won't Start After Cleanup

```bash
# Reinstall dependencies
cd backend-py
pip install -r requirements.txt

# Reinstall Playwright
playwright install chromium

# Verify Ollama
ollama list
```

## Additional Resources

- [WSL Storage Documentation](https://docs.microsoft.com/en-us/windows/wsl/disk-space)
- [Docker Cleanup Guide](https://docs.docker.com/config/pruning/)
- [Pip Cache Documentation](https://pip.pypa.io/en/stable/topics/caching/)
