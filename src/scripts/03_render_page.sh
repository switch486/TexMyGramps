#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PAGES_DIR="$ROOT_DIR/pages"
PAGE_NAME="${1:-}"

if [ -z "$PAGE_NAME" ]; then
  echo "Usage: $0 <page-name>"
  exit 1
fi

PAGE_DIR="$PAGES_DIR/$PAGE_NAME"
if [ ! -d "$PAGE_DIR" ]; then
  echo "ERROR: page directory not found: $PAGE_DIR"
  exit 1
fi

OUTPUT_DIR="$PAGE_DIR/output"

mkdir -p "$OUTPUT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to render TeX"
  exit 1
fi

if ! command -v tectonic >/dev/null 2>&1; then
  echo "ERROR: tectonic command not found in PATH"
  exit 1
fi

GENERATED_TEX="$OUTPUT_DIR/page.tex"
python3 "$ROOT_DIR/scripts/render_person_tex.py" --page-dir "$PAGE_DIR" --output-file "$GENERATED_TEX"

if [ ! -f "$GENERATED_TEX" ]; then
  echo "ERROR: generated TeX not found: $GENERATED_TEX"
  exit 1
fi

echo "Building page '$PAGE_NAME' with local tectonic"
tectonic --outdir "$OUTPUT_DIR" "$GENERATED_TEX"

echo "Build complete. Output written to: $OUTPUT_DIR"
