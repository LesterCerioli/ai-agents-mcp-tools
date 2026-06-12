#!/usr/bin/env bash
# Run this script on a Windows machine or GitHub Actions Windows runner.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/app/cli/dist"

echo "Building Windows binary..."

cd "$ROOT"

pyinstaller \
  --onefile \
  --name agents-windows \
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

echo "Done: $DIST/agents-windows.exe"
