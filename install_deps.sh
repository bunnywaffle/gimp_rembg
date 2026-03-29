#!/usr/bin/env bash
# install_deps.sh — Install rembg into the plugin's venv
# Run this if you prefer the terminal over Rembg > Setup... in GIMP.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== GIMP Rembg Setup ==="

# Check Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found. Install it first."
    exit 1
fi

echo "Using: $PYTHON ($($PYTHON --version))"

# Remove old venv
if [ -d "$VENV_DIR" ]; then
    echo "Removing old venv..."
    rm -rf "$VENV_DIR"
fi

# Create venv
echo "Creating venv..."
"$PYTHON" -m venv "$VENV_DIR"

# Install
echo "Upgrading pip..."
"$VENV_DIR/bin/pip" install --upgrade pip

echo "Installing rembg (this may take a few minutes)..."
"$VENV_DIR/bin/pip" install pillow onnxruntime rembg

# Verify
echo "Verifying..."
"$VENV_DIR/bin/python" -c "import rembg; print(f'rembg {rembg.__version__} installed!')"

echo ""
echo "Done! Restart GIMP and use Rembg > Remove Background..."
