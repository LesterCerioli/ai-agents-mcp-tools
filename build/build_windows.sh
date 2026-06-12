#!/usr/bin/env bash
# Run this script on a Windows machine or GitHub Actions Windows runner.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/app/cli/dist"

if [ -z "$AGENTS_API_URL" ]; then
    echo "ERROR: AGENTS_API_URL environment variable is required."
    echo "Usage: AGENTS_API_URL=https://your-api.com bash build/build_windows.sh"
    exit 1
fi

echo "Building Windows binary (API: $AGENTS_API_URL)..."

cd "$ROOT"

# Generate build-time config so the URL is baked into the binary
cat > "$ROOT/app/cli/_build_config.py" <<EOF
# Generated at build time — do not edit manually.
AGENTS_API_URL = "$AGENTS_API_URL"
EOF

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
