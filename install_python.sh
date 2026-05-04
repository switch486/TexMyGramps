#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
  echo "ERROR: requirements.txt not found at $REQUIREMENTS_FILE"
  exit 1
fi

PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python)"
else
  echo "ERROR: Python is not installed. Install Python 3 first."
  exit 1
fi

echo "Using Python: $PYTHON_CMD"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

PIP_CMD="$VENV_DIR/bin/pip"
if [ ! -x "$PIP_CMD" ]; then
  echo "ERROR: pip not found in virtual environment"
  exit 1
fi

echo "Upgrading pip"
"$PIP_CMD" install --upgrade pip

echo "Installing Python dependencies from requirements.txt"
"$PIP_CMD" install -r "$REQUIREMENTS_FILE"

echo "Python environment ready. Activate with: source $VENV_DIR/bin/activate"
