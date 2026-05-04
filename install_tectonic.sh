#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v tectonic >/dev/null 2>&1; then
  echo "tectonic is already installed: $(command -v tectonic)"
  exit 0
fi

echo "tectonic command not found. Attempting installation..."

if command -v brew >/dev/null 2>&1; then
  echo "Installing tectonic via Homebrew"
  brew install tectonic
  exit 0
fi

if command -v cargo >/dev/null 2>&1; then
  echo "Installing tectonic via cargo"
  cargo install tectonic
  echo "tectonic installed via cargo"
  exit 0
fi

echo "ERROR: No supported installer found."
echo "Install Homebrew and run: brew install tectonic"
echo "Or install Rust and Cargo, then run: cargo install tectonic"
exit 1
