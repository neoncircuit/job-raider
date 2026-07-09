# Docker Storage and Disk Space Requirements

## Critical WSL2/Docker Storage Issue

**IMPORTANT:** Docker Desktop on Windows stores ALL data on C: drive by default, even if your project is on D: or E: drive.

### The Problem

Docker Desktop uses `C:\Program Files\Docker\Docker\resources` which mounts as `D:` drive in containers. This means:
- Docker images (10GB+ for this project)
- Container filesystems
- WSL2 distributions
- Volumes and cached data

**ALL get stored on C: drive**, not your project drive.

### Current Project Storage Requirements

**Minimum Requirements:**
- **C: drive**: 200GB+ free space (Docker + WSL2 + growth room)
- **D:/E: drive** (project drive): 50GB+ free space

**Recommended for Development:**
- **C: drive**: 300GB+ free space
- **D:/E: drive** (project drive): 100GB+ free space

### What This Project Uses

#### Docker Images (~15-20GB)
- `job-raider-backend`: 9.94GB (CUDA + Python + Ollama + dependencies)
- `job-raider-frontend`: 629MB
- `ollama/ollama`: Varies by model size (2-10GB per model)
- Build cache: 5-10GB

#### Project Data (~10-20GB)
- `data/`: Scraped job listings, profiles, applications
- `data/cache/`: LLM response cache
- `.venv/`: Python virtual environment
- `notebooks/`: Jupyter notebooks

#### Docker Overhead (~30-50GB)
- Container filesystem layers
- WSL2 VHDX files
- Docker logs and metrics
- Volume snapshots

**Total C: drive usage: 80-120GB for this project**

### Actual Breakdown Example

On a typical development system, WSL2 Ubuntu may consume ~105GB:

**WSL2 Home Directory (~38GB):**
- `~/.cache/pip`: 14GB - Python package downloads
- `~/.cache/huggingface`: 12GB - Downloaded ML models
- `~/.cache/ms-playwright`: 1.2GB - Browser automation
- `~/.cache/puppeteer`: 626MB - Browser automation

**WSL2 System Directory (~31GB):**
- `/usr/share/ollama`: 14GB - Ollama models
- `/usr/lib`: 12GB - System libraries
- `/usr/local/lib`: 4.7GB - Installed packages

**Docker Data (~50GB):**
- Build cache: 36.74GB
- Images: ~20GB (job-raider-backend 9.94GB, ollama 6.29GB, etc.)
- Volumes: ~7.7GB (ollama-data 6.6GB)

## Solutions

### Option 1: Move Docker Data to D: Drive (RECOMMENDED)

1. **Stop Docker Desktop**
2. **Move Docker data directory:**
   ```powershell
   # In PowerShell as Administrator
   $wsl = Get-ChildItem HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss
   $wsl.GetValue("BasePath") # Shows current location
   
   # Stop WSL
   wsl --shutdown
   
   # Move WSL distro to D: (takes 10-30 minutes)
   wsl --export Ubuntu D:\wsl-ubuntu.tar
   wsl --unregister Ubuntu
   wsl --import D:\wsl-ubuntu D:\wsl-ubuntu.tar
   ```

3. **Configure Docker Desktop:**
   - Settings → Resources → WSL Integration
   - Enable "Expose my WSL2 file system to Windows"
   - This keeps data on D: drive

4. **Configure Project Data:**
   - Already on D: drive ✓
   - Add D: drive symlink if needed

### Option 3: Use WSL2 Directly (Recommended for Development)

Skip Docker Desktop, use WSL2 directly:
- Stores everything on D: drive
- No Docker Desktop overhead
- Better performance
- Native Linux filesystem

### Option 3: Clean Up Unused Resources (RECOMMENDED - First Step)

Before moving Docker data, try these cleanup commands to reclaim space:

**WSL2 Cleanup:**
```bash
# Clear pip cache (can be 10-20GB)
pip cache purge

# Check HuggingFace cache usage
du -sh ~/.cache/huggingface

# List cached HuggingFace models
ls -lah ~/.cache/huggingface/hub/

# Remove specific HuggingFace models if no longer needed
rm -rf ~/.cache/huggingface/hub/models--<model-name>
```

**Docker Cleanup:**
```bash
# Remove build cache (can be 30-40GB)
docker builder prune -af

# Remove unused images (dangling)
docker image prune -af

# Remove stopped containers
docker container prune -f

# See detailed breakdown
docker system df -v

# Remove everything unused (WARNING: cannot be undone)
docker system prune -af --volumes
```

**Expected Space Recovery:**
- pip cache: 10-20GB
- Docker build cache: 30-40GB
- Unused images: 5-15GB

### Option 4: Move Docker Data to D: Drive

```bash
# Remove unused Docker images
docker image prune -a

# Remove stopped containers
docker container prune

# Remove build cache
docker builder prune

# Remove unused volumes
docker volume prune

# Check Docker space usage
docker system df
```

### Option 5: Move Docker Desktop Data Directory

1. Stop Docker Desktop
2. Move `%LOCALAPPDATA%\Docker\wsl` to D: drive
3. Update Docker Desktop settings

## Setup Script Additions

Add to `setup.sh`:

```bash
# Check C: drive space before starting
check_disk_space() {
    print_status "Checking available disk space..."
    
    # Check C: drive (Windows + Docker location)
    C_AVAILABLE=$(df /mnt/c | tail -1 | awk '{print $4}' | sed 's/%//')
    C_AVAILABLE_GB=$(echo "$C_AVAILABLE" | awk '{printf "%.0f", $1/1024/1024/1024}')
    
    if [ "$C_AVAILABLE_GB" -lt 200 ]; then
        print_error "WARNING: Less than 200GB available on C: drive"
        print_error "Docker Desktop + WSL2 requires ~100GB+ for this project"
        print_error "Consider freeing up space or moving Docker to D: drive"
        print_warning "See docs/docker-storage.md for solutions"
    fi
}
```

## Monitoring Disk Space

### Check Docker Usage
```bash
# Docker disk usage
docker system df -v

# Individual image sizes
docker images --format "table {{.Repository}}\t{{.Size}}\t{{.VirtualSize}}"

# Volume sizes
docker system df -v | grep -A 20 "Volumes"
```

### Check Project Data Usage
```bash
# From project root
du -sh data/ apps/backend-py/.venv/
du -sh apps/backend-py/data/
```

## Before Starting Development

1. **Check C: drive space**: Ensure 200GB+ free
2. **Check D: drive space**: Ensure 100GB+ free for project
3. **Run cleanup commands first**: See Option 3 for immediate space recovery
4. **Consider moving Docker to D: drive**: See Option 4 if cleanup is insufficient

## Ollama Model Storage

Ollama stores models in:
- Docker Desktop: `\\wsl$\.ollama\models` (on C:)
- WSL2 Direct: `~/.ollama/models` (on D: if configured)

**Model Sizes:**
- qwen2.5:3b: ~2GB
- qwen2.5:7b: ~4GB
- qwen2.5:14b: ~9GB
- qwen2.5:32b: ~20GB

**Recommendation:** Use qwen2.5:7b or smaller for 8GB VRAM GPU.

## WSL2 Backing Files

WSL2 uses a VHDX file that grows as you use it:
- Location: `C:\Users\<user>\AppData\Local\Docker\wsl`
- Size: Can grow 50-100GB
- Growth happens during: package installs, Docker builds, large file operations

**To compact:**
```powershell
# Optimize WSL2 VHDX (requires shutdown)
wsl --shutdown
Optimize-VHD -Path "C:\Users\<user>\AppData\Local\Docker\wsl\docker-desktop-data\ext4.vhdx"
```

## Summary

**For this project, expect to use:**
- C: drive: 80-120GB (Docker Desktop, WSL2, Ollama models, caches)
- D: drive: 20-50GB (project files, data)

**To reclaim space immediately (try first):**
```bash
# Clear pip cache (10-20GB)
pip cache purge

# Clear Docker build cache (30-40GB)
docker builder prune -af

# Remove unused Docker images (5-15GB)
docker image prune -af
```

**If more space is needed:**
1. Move Docker data to D: drive (see Option 4)
2. Use WSL2 directly instead of Docker Desktop (see Option 3)

**Before starting, ensure:**
1. C: drive has 200GB+ free (or run cleanup first)
2. D: drive has 100GB+ free for project data
3. Consider moving Docker to D: drive if space is tight

**See Also:**
- [Troubleshooting](troubleshooting.md) - Disk space issues
- [Architecture](architecture.md) - Storage architecture
- [Usage Guide](usage.md) - Setup instructions
