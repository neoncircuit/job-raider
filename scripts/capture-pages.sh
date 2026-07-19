#!/usr/bin/env bash
# Capture full-page screenshots of every frontend route.
#
# Usage:
#   ./scripts/capture-pages.sh                 # capture all pages
#   ./scripts/capture-pages.sh profile jobs    # capture specific routes
#
# Env overrides:
#   BASE_URL  (default: http://localhost:3000)
#   OUT_DIR   (default: /tmp/jr-shots)
#
# Screenshots land in OUT_DIR as <route>.png. Claude can then review them
# via its Read tool — no manual image uploads needed.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3000}"
OUT_DIR="${OUT_DIR:-/tmp/jr-shots}"

ALL_ROUTES=(
  dashboard
  pipeline
  jobs
  cover-letter
  career-coach
  applications
  profile
  assessment
  resume-analysis
  linkedin-analysis
  metrics
  settings
)

ROUTES=("${@:-${ALL_ROUTES[@]}}")

mkdir -p "$OUT_DIR"

echo "Capturing ${#ROUTES[@]} page(s) from $BASE_URL -> $OUT_DIR"
for route in "${ROUTES[@]}"; do
  out="$OUT_DIR/${route}.png"
  echo "  /$route -> $out"
  npx playwright screenshot \
    --browser=chromium \
    --viewport-size=1440,900 \
    --full-page \
    --wait-for-timeout=4000 \
    "$BASE_URL/$route" "$out" >/dev/null
done

echo "Done. $(ls -1 "$OUT_DIR" | wc -l) file(s) in $OUT_DIR"
