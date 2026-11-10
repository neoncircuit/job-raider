#!/bin/bash
# Quick container rebuild for development
# Usage: ./docker-rebuild.sh [service]
#
# The images contain the code (only apps/backend-py/data is mounted), so a
# code change needs a new image. --build rebuilds the image from the current
# files; --force-recreate then starts a new container from it.

if [ -n "$1" ]; then
    # Rebuild specific service
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose down "$1"
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose up -d --build --force-recreate "$1"
else
    # Rebuild all
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose down
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose up -d --build --force-recreate
fi
