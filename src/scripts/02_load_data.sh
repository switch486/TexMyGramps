#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PAGES_DIR="$ROOT_DIR/pages"
CONFIG_FILE="$ROOT_DIR/scripts/gramps_api.env"
LOCAL_CONFIG_FILE="$ROOT_DIR/scripts/gramps_api.local.env"
TOKEN_FILE="$ROOT_DIR/scripts/gramps_api_token.env"

# Load environment variables from .env files
# Try multiple common filenames so we pick up MAPBOX_TOKEN and other config
for env_file in "$CONFIG_FILE" "$LOCAL_CONFIG_FILE" "$TOKEN_FILE"; do
    if [[ -f "$env_file" ]]; then
        echo "[ENV] Loading environment from: $env_file"
        set +u
        set -a
        source "$env_file"
        set +a
        set -u
    fi
done

PAGE_NAME="${1:-}"
STAGE="${2:-}"
PERSON_ID="${3:-}"
if [ -z "$PAGE_NAME" ]; then
  echo "Usage: $0 <page-name> [stage] [person-id]"
  exit 1
fi

if [ -n "$STAGE" ]; then
  PAGES_DIR="$ROOT_DIR/pages_$STAGE"
fi

PAGE_DIR="$PAGES_DIR/$PAGE_NAME"
if [ ! -d "$PAGE_DIR" ]; then
  echo "ERROR: page directory not found: $PAGE_DIR"
  exit 1
fi

SOURCE_FILE="$PAGE_DIR/source.json"
if [ -z "$PERSON_ID" ]; then
  if [ ! -f "$SOURCE_FILE" ]; then
    echo "ERROR: source ID file not found: $SOURCE_FILE"
    exit 1
  fi
fi

OUTPUT_DIR="$PAGE_DIR/output"
ASSETS_DIR="$PAGE_DIR/assets"
DATA_FILE="$ASSETS_DIR/data.json"
rm -rf "$ASSETS_DIR"
mkdir -p "$ASSETS_DIR"
mkdir -p "$OUTPUT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to run the GRAMPS loader"
  exit 1
fi

export GRAMPS_API_BASE_URL \
  GRAMPS_API_TOKEN \
  GRAMPS_API_PERSON_QUERY_PARAM \
  GRAMPS_API_PERSON_SEARCH_PATH \
  GRAMPS_API_EVENT_DETAIL_PATH \
  GRAMPS_API_PLACE_DETAIL_PATH \
  GRAMPS_API_TIMEOUT

python3 "$ROOT_DIR/scripts/gramps_api_loader.py" \
  --source-file "$SOURCE_FILE" \
  --output "$DATA_FILE" \
  --assets-dir "$ASSETS_DIR"

echo "Loaded GRAMPS data for page '$PAGE_NAME' into $DATA_FILE"
