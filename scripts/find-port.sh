#!/bin/bash
# Find an available port starting from a given port

find_port() {
    local start_port=${1:-8000}
    local max_attempts=${2:-100}
    local port=$start_port

    for i in $(seq 1 $max_attempts); do
        if ! netstat -an 2>/dev/null | grep -q ":$port " && \
           ! lsof -i ":$port" >/dev/null 2>&1 && \
           ! nc -z localhost $port 2>/dev/null; then
            echo $port
            return 0
        fi
        port=$((port + 1))
    done

    echo "No available port found starting from $start_port" >&2
    return 1
}

# If script is executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    find_port "${1:-8000}"
fi
