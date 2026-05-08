#!/bin/bash
set -e

echo "Job Raider - Entrypoint"

# Fix WSL2 DrvFs caching issues
# This fixes cases where bind mounts don't reflect recent changes
echo "Checking for common import issues..."

# Fix 1: Remove invalid pydantic imports that may be cached
if grep -q "field_serializer_validator" /app/src/models/user_profile.py 2>/dev/null; then
    echo "Fixing invalid pydantic import in user_profile.py..."
    sed -i 's/, field_serializer_validator//g' /app/src/models/user_profile.py
fi

# Fix 2: Remove other common invalid imports
for file in /app/src/models/*.py; do
    if [ -f "$file" ]; then
        # Fix field_serializer_validator
        sed -i 's/, field_serializer_validator//g' "$file"
        # Fix any other common pydantic v2 issues
        sed -i 's/from pydantic import \([^\]*\), field_serializer_validator/from pydantic import \1/g' "$file"
    fi
done

echo "Import fixes complete."

# Install Playwright browsers if not already installed
if [ ! -d "/home/jobraider/.cache/ms-playwright/chromium-1208" ]; then
    echo "Playwright browsers not found. Installing..."
    playwright install chromium || echo "Warning: Playwright browser install failed, will retry on demand"
fi

# Execute the main command
exec "$@"
