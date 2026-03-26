#!/bin/bash
# =========================================================
# VectorMap — Automated Setup Script
# =========================================================
# This script bootstraps the entire VectorMap Agentic AI
# environment from scratch on any macOS / Linux machine.
#
# Usage:
#   cd VectorBrain
#   chmod +x setup.sh
#   bash setup.sh
#
# Prerequisites:
#   - Python 3.9+
#   - Ollama installed (https://ollama.com)
#   - Git (for cloning, if applicable)
# =========================================================

set -e  # Exit immediately on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║       VECTORMAP ENVIRONMENT BOOTSTRAPPER           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# -----------------------------------------------
# Step 1: Create Python Virtual Environment
# -----------------------------------------------
VENV_DIR="$SCRIPT_DIR/agent_env"

if [ -d "$VENV_DIR" ]; then
    echo "✅ Virtual environment already exists at: $VENV_DIR"
else
    echo "🔧 Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment created."
fi

# -----------------------------------------------
# Step 2: Activate and Install Dependencies
# -----------------------------------------------
echo "📦 Installing Python dependencies from requirements.txt..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo "✅ All dependencies installed."

# -----------------------------------------------
# Step 3: Verify Ollama is Running
# -----------------------------------------------
echo ""
echo "🔍 Checking for Ollama LLM runtime..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama binary found."
    
    # Check if the required model is available
    if ollama list 2>/dev/null | grep -q "qwen2.5-coder:7b"; then
        echo "✅ Model 'qwen2.5-coder:7b' is available."
    else
        echo "⚠️  Model 'qwen2.5-coder:7b' not found. Pulling now..."
        ollama pull qwen2.5-coder:7b
        echo "✅ Model pulled successfully."
    fi
else
    echo "❌ Ollama is not installed."
    echo "   Install it from: https://ollama.com"
    echo "   Then run: ollama pull qwen2.5-coder:7b"
    echo ""
fi

# -----------------------------------------------
# Step 4: Create data directories if missing
# -----------------------------------------------
echo ""
echo "📂 Ensuring data directories exist..."
mkdir -p "$SCRIPT_DIR/data/chroma_db_test"
mkdir -p "$SCRIPT_DIR/data/Vector_Obsidian_Vault_TEST"
mkdir -p "$SCRIPT_DIR/data/Repositories"
echo "✅ Data directories verified."

# -----------------------------------------------
# Step 5: Print Launch Instructions
# -----------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║            SETUP COMPLETE — READY TO LAUNCH          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  To start the VectorMap Operations Center:"
echo ""
echo "    source agent_env/bin/activate"
echo "    python src/server.py"
echo ""
echo "  The browser will open automatically to the dashboard."
echo "  Use the 'UPDATE VAULT CACHE' button to index your"
echo "  Obsidian Vault into ChromaDB on first run."
echo ""
echo "═══════════════════════════════════════════════════════"
