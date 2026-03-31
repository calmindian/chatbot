#!/usr/bin/env bash
# ============================================================
#  AI Friend -- Starting
# ============================================================

set -euo pipefail
cd "$(dirname "$0")"

echo
echo "============================================================"
echo " AI Friend -- Starting"
echo "============================================================"
echo

# ── Check Ollama is running ───────────────────────────────────
echo "Checking Ollama service..."
if ! curl -sf http://localhost:11434/ > /dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve >> /tmp/ollama.log 2>&1 &
    echo "Waiting for Ollama to be ready..."
    for i in $(seq 1 15); do
        curl -sf http://localhost:11434/ > /dev/null 2>&1 && break
        echo "  Waiting... ($i/15)"
        sleep 2
    done
    curl -sf http://localhost:11434/ > /dev/null 2>&1 || {
        echo "ERROR: Ollama did not start in time. Check /tmp/ollama.log for details."
        exit 1
    }
    echo "Ollama started -- OK."
else
    echo "Ollama already running -- OK."
fi

# ── Activate venv and start FastAPI ──────────────────────────
echo "Starting FastAPI on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."
echo

# shellcheck disable=SC1091
source venv/bin/activate
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
