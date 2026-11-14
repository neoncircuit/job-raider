#!/bin/bash
# Job Raider - find a Python that meets .python-version
#
# Sourced by setup.sh and scripts/dev.sh. A fresh machine can have an old
# default python3 (Ubuntu 22.04 has 3.10) next to a newer versioned Python
# (python3.12). find_python picks the newest suitable one.
#
# When there is none, ensure_python installs one inside the repository: it
# downloads a pinned uv (checked against its SHA-256) into .tools/bin, and uv
# installs the .python-version Python into .tools/python. Nothing is written
# outside the repository and nothing needs sudo. .tools/ is git-ignored.

# Print the major.minor that .python-version requires (for example 3.11).
# Args: $1 = project root.
python_required_version() {
    tr -d '[:space:]' < "$1/.python-version" | cut -d'.' -f1,2
}

# Return 0 when the Python command $1 runs and is at least version $2.
python_meets() {
    local version
    version="$("$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2> /dev/null)" || return 1
    [ -n "$version" ] || return 1
    [ "$(printf '%s\n' "$2" "$version" | sort -V | head -n1)" = "$2" ]
}

# Pinned uv for the in-repository Python (a release at least two weeks old).
UV_VERSION="0.13.5"
# SHA-256 of the uv release archives, from the release's .sha256 files.
UV_SHA256_x86_64="f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f"
UV_SHA256_aarch64="4bb69cf95ed13f23713bb7bc09f241896ea0c75b7c557e615a20604b82f9c403"

# Print the newest Python command that meets .python-version; return 1 if none.
# The system Pythons come first, then a Python that ensure_python installed in
# .tools/python.
# Args: $1 = project root.
find_python() {
    local required candidate
    required="$(python_required_version "$1")"
    for candidate in python3.14 python3.13 python3.12 python3.11 python3 \
        "$1"/.tools/python/cpython-*/bin/python3; do
        if command -v "$candidate" &> /dev/null && python_meets "$candidate" "$required"; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

# Install the .python-version Python inside the repository with a pinned uv.
# All output goes to stderr, so callers can capture the path from ensure_python.
# Args: $1 = project root.
# Returns: 0 when the install finished, 1 on any failure.
install_repo_python() {
    local root="$1" arch sha archive tmp
    case "$(uname -m)" in
        x86_64) arch="x86_64"; sha="$UV_SHA256_x86_64" ;;
        aarch64 | arm64) arch="aarch64"; sha="$UV_SHA256_aarch64" ;;
        *) echo "No pinned uv for $(uname -m)." >&2; return 1 ;;
    esac
    archive="uv-$arch-unknown-linux-gnu.tar.gz"
    mkdir -p "$root/.tools/bin"
    if [ ! -x "$root/.tools/bin/uv" ] || ! "$root/.tools/bin/uv" --version 2> /dev/null | grep -q " $UV_VERSION"; then
        echo "Downloading uv $UV_VERSION into .tools/bin..." >&2
        tmp="$(mktemp -d "$root/.tools/download.XXXXXX")"
        if ! curl -fsSL -o "$tmp/$archive" \
            "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$archive"; then
            echo "Could not download uv (check the network)." >&2
            rm -rf "$tmp"; return 1
        fi
        if ! echo "$sha  $tmp/$archive" | sha256sum -c --quiet - > /dev/null 2>&1; then
            echo "The uv download does not match its SHA-256. Stopped." >&2
            rm -rf "$tmp"; return 1
        fi
        tar -xzf "$tmp/$archive" -C "$tmp"
        mv "$tmp/uv-$arch-unknown-linux-gnu/uv" "$root/.tools/bin/uv"
        rm -rf "$tmp"
    fi
    echo "Installing Python $(python_required_version "$root") into .tools/python..." >&2
    # The cache and the install stay in .tools; --no-bin writes no links to ~/.local/bin.
    UV_CACHE_DIR="$root/.tools/cache" UV_PYTHON_INSTALL_DIR="$root/.tools/python" \
        UV_NO_CONFIG=1 "$root/.tools/bin/uv" python install --no-bin \
        "$(python_required_version "$root")" >&2
}

# Print a suitable Python, installing one in .tools when none exists.
# Args: $1 = project root.
# Returns: 0 with the path on stdout; 1 when no Python could be found or installed.
ensure_python() {
    find_python "$1" && return 0
    echo "No Python $(python_required_version "$1") or newer found on this machine." >&2
    install_repo_python "$1" || return 1
    find_python "$1"
}

# Print what was found and the commands that install a suitable Python.
# Args: $1 = project root.
python_install_help() {
    local required found
    required="$(python_required_version "$1")"
    found="$(python3 --version 2> /dev/null || echo "no python3")"
    echo "Python $required or newer is required (found: $found)."
    echo "The automatic install into .tools/python did not work (see above)."
    echo "Install Python 3.12 next to the system Python (do not replace python3):"
    echo "  Ubuntu 22.04:"
    echo "    sudo add-apt-repository -y ppa:deadsnakes/ppa"
    echo "    sudo apt update && sudo apt install -y python3.12 python3.12-venv"
    echo "  Ubuntu 24.04 or later:"
    echo "    sudo apt update && sudo apt install -y python3 python3-venv"
    echo "Then run this script again."
}
