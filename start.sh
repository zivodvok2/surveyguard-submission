#!/usr/bin/env bash
# SurveyGuard — single-command startup
# Runs the FastAPI backend on port 8000; the pre-built React frontend
# is served from datasense-ui/dist/ — no separate dev server needed.
#
# Usage:
#   chmod +x start.sh
#   ./start.sh            # default port 8000
#   PORT=9000 ./start.sh  # custom port

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Python dependency check ─────────────────────────────────────────────────
if ! python3 -c "import fastapi, uvicorn" &>/dev/null; then
  echo "Installing Python dependencies..."
  pip3 install -r requirements.txt --break-system-packages -q
fi

# ── .env check ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "ERROR: .env file not found."
  echo "Copy .env.example and fill in BOOTSTRAP_ADMIN_PASSWORD at minimum:"
  echo "  cp .env.example .env"
  exit 1
fi

if ! grep -q "BOOTSTRAP_ADMIN_PASSWORD=." .env; then
  echo "ERROR: BOOTSTRAP_ADMIN_PASSWORD is not set in .env."
  echo "Add a password to .env before starting:"
  echo "  echo 'BOOTSTRAP_ADMIN_PASSWORD=your-password' >> .env"
  exit 1
fi

# ── Frontend build check ─────────────────────────────────────────────────────
if [ ! -f "datasense-ui/dist/index.html" ]; then
  echo "Frontend dist not found — building now..."
  cd datasense-ui
  npm install -q
  npm run build
  cd "$ROOT"
fi

# ── Start ────────────────────────────────────────────────────────────────────
PORT="${PORT:-8000}"
echo ""
echo "  SurveyGuard starting on http://localhost:${PORT}"
echo "  Press Ctrl+C to stop."
echo ""

PORT="$PORT" python3 start.py
