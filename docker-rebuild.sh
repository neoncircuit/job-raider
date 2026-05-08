#!/bin/bash
# Quick container rebuild for development
# Usage: ./docker-rebuild.sh [service]

if [ -n "$1" ]; then
    # Rebuild specific service
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose down "$1"
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose up -d --force-recreate "$1"
else
    # Rebuild all
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose down
    /mnt/c/Program\ Files/Docker/Docker/resources/bin/docker.exe compose up -d --force-recreate
fi
