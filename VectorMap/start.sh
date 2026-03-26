#!/bin/bash
# ─── VectorMap — Quick Start Script ──────────────────────────────────────────
# Activates the virtual environment and launches the VectorMap server.
# The dashboard will open automatically in your default browser.
#
# Usage:
#   bash start.sh
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/agent_env"

# Verify the virtual environment exists
if [ ! -f "$VENV/bin/activate" ]; then
    echo "❌  Virtual environment not found at: $VENV"
    echo "    Run setup first:  bash setup.sh"
    exit 1
fi

# Activate and launch
source "$VENV/bin/activate"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║          VectorMap — Starting Dashboard              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

cd "$SCRIPT_DIR"
python src/server.py
