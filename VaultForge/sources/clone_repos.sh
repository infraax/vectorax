#!/usr/bin/env bash
# clone_repos.sh — Clone all Vector robot source repositories
#
# Usage:
#   bash VaultForge/sources/clone_repos.sh
#
# Clones all repos listed in REPOS.yaml into VaultForge/sources/repositories/
# Safe to re-run — skips repos that already exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_DIR="$SCRIPT_DIR/repositories"

mkdir -p "$REPOS_DIR"

declare -A REPOS=(
  [vector]="https://github.com/digital-dream-labs/vector.git"
  [vector-python-sdk]="https://github.com/fforchino/vector-python-sdk.git"
  [vector-go-sdk]="https://github.com/fforchino/vector-go-sdk.git"
  [vector-cloud]="https://github.com/digital-dream-labs/vector-cloud.git"
  [wire-pod]="https://github.com/kercre123/wire-pod.git"
  [vector-bluetooth]="https://github.com/digital-dream-labs/vector-bluetooth.git"
  [chipper]="https://github.com/digital-dream-labs/chipper.git"
  [vector-web-setup]="https://github.com/digital-dream-labs/vector-web-setup.git"
  [vectorx]="https://github.com/fforchino/vectorx.git"
  [vectorx-voiceserver]="https://github.com/fforchino/vectorx-voiceserver.git"
  [escape-pod-extension]="https://github.com/digital-dream-labs/escape-pod-extension.git"
  [dev-docs]="https://github.com/digital-dream-labs/dev-docs.git"
  [hugh]="https://github.com/digital-dream-labs/hugh.git"
)

echo "Cloning ${#REPOS[@]} Vector repositories into $REPOS_DIR"
echo ""

for name in "${!REPOS[@]}"; do
  url="${REPOS[$name]}"
  dest="$REPOS_DIR/$name"
  if [ -d "$dest/.git" ]; then
    echo "  ✓ $name — already cloned, skipping"
  else
    echo "  ↓ $name — cloning from $url"
    git clone --depth=1 "$url" "$dest" 2>&1 | tail -1
  fi
done

echo ""
echo "Done. Repos in: $REPOS_DIR"
echo "Next step: run the VaultForge pipeline to rebuild ChromaDB"
echo "  cd VaultForge && python pipeline/db_writer.py"
