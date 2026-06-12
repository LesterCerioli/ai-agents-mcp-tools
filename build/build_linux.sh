#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/app/cli/dist"

if [ -z "$AGENTS_API_URL" ]; then
    echo "ERROR: AGENTS_API_URL environment variable is required."
    echo "Usage: AGENTS_API_URL=https://your-api.com bash build/build_linux.sh"
    exit 1
fi

echo "Building Linux binary (API: $AGENTS_API_URL)..."

cd "$ROOT"

source venv/bin/activate 2>/dev/null || true

pyinstaller \
  --onefile \
  --name agents-linux \
  --distpath "$DIST" \
  --workpath /tmp/pyinstaller-build \
  --specpath /tmp/pyinstaller-spec \
  --hidden-import app.cli.platforms.linux \
  --hidden-import app.cli.platforms.windows \
  --hidden-import app.cli.client \
  --hidden-import rich \
  --hidden-import httpx \
  --hidden-import typer \
  app/cli/commands.py

echo "Done: $DIST/agents-linux"
