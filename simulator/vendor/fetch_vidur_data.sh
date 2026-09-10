#!/usr/bin/env bash
# Fetch the Vidur profiling data and processed traces that are too large to
# commit, at the exact commit pinned by D-006.
#
# Usage:  bash simulator/vendor/fetch_vidur_data.sh [dest]
# Default dest: simulator/vendor/vidur/data  (git-ignored via the `data/` rule)
#
# Downloads ~584 MB. Safe to re-run; skips if the destination already exists.

set -euo pipefail

VIDUR_SHA="25e0082dbbfb206fb0477c3ebbededa7ead78949"
VIDUR_URL="https://github.com/microsoft/vidur.git"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-${SCRIPT_DIR}/vidur/data}"

if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    echo "[fetch_vidur_data] $DEST already populated; nothing to do."
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "[fetch_vidur_data] cloning Vidur at ${VIDUR_SHA:0:7} (data only, no history)..."
git clone --filter=blob:none --no-checkout --quiet "$VIDUR_URL" "$TMP/vidur"
git -C "$TMP/vidur" sparse-checkout set --no-cone data
git -C "$TMP/vidur" checkout --quiet "$VIDUR_SHA"

mkdir -p "$(dirname "$DEST")"
mv "$TMP/vidur/data" "$DEST"

echo "[fetch_vidur_data] done. $(du -sh "$DEST" | cut -f1) at $DEST"
echo "[fetch_vidur_data] NOTE: data/processed_traces/mooncake_conversation_trace.csv"
echo "[fetch_vidur_data]       is upstream's preprocessing. Per falsifier F4 we do NOT"
echo "[fetch_vidur_data]       take it on trust — see workloads/ for our re-derivation."
