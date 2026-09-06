#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[StorServer] Atualizando código..."
git pull --ff-only origin main

echo "[StorServer] Aplicando atualização..."
bash ./install.sh
