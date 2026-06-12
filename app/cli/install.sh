#!/usr/bin/env bash
set -e

API_BASE="__API_BASE_URL__"
INSTALL_DIR="/usr/local/bin"
BINARY_NAME="agents"

OS="$(uname -s)"

echo "Installing Agents CLI..."

if [ "$OS" = "Linux" ]; then
    DOWNLOAD_URL="$API_BASE/cli/download/linux"
elif [ "$OS" = "Darwin" ]; then
    DOWNLOAD_URL="$API_BASE/cli/download/linux"
else
    echo "Unsupported OS: $OS"
    echo "For Windows, download manually from: $API_BASE/cli/download/windows"
    exit 1
fi

TMP_FILE="$(mktemp)"

echo "Downloading binary..."
curl -fsSL "$DOWNLOAD_URL" -o "$TMP_FILE"
chmod +x "$TMP_FILE"

if [ -w "$INSTALL_DIR" ]; then
    mv "$TMP_FILE" "$INSTALL_DIR/$BINARY_NAME"
else
    sudo mv "$TMP_FILE" "$INSTALL_DIR/$BINARY_NAME"
fi

echo ""
echo "✓ Agents CLI installed successfully!"
echo ""
echo "Try it:"
echo "  agents version"
echo "  agents generate \"my project description\" --name my-project"
