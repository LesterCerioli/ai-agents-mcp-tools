#!/usr/bin/env bash
set -e

API_BASE="__API_BASE_URL__"
INSTALL_DIR="/usr/local/bin"
BINARY_NAME="agents"

OS="$(uname -s)"

echo "Installing Agents CLI (Grok-powered)..."
echo "Backend: Grok (xAI) forçado via GROCK_API_TOKEN + Skills"
echo ""

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
echo "✓ Agents CLI installed successfully! (Grok + Skills)"
echo ""
echo "Try it:"
echo "  agents version"
echo "  agents ask \"avaliar meu projeto e adicionar autenticação JWT\" --path ./my-project"
echo "  agents improve \"adicionar pagamento com cartão e gateway\" --path ./my-api"
echo "  agents generate \"Go e-commerce API with Fiber, PostgreSQL, JWT\" --name store-api"
echo ""
echo "O servidor usa Grok (xAI) forçado via GROCK_API_TOKEN para entender requisitos"
echo "e gerar/corrigir código junto com as 100+ skills. Configure GROCK_API_TOKEN no .env do servidor."
echo "New commands ship over time — run 'agents update' anytime to get the latest version."
