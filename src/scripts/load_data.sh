#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PAGES_DIR="$ROOT_DIR/pages"
CONFIG_FILE="$ROOT_DIR/scripts/gramps_api.env"
LOCAL_CONFIG_FILE="$ROOT_DIR/scripts/gramps_api.local.env"
TOKEN_FILE="$ROOT_DIR/scripts/gramps_api_token.env"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: GRAMPS API config not found: $CONFIG_FILE"
  exit 1
fi

source "$CONFIG_FILE"

# Load local credentials if available (overrides values in main config)
if [ -f "$LOCAL_CONFIG_FILE" ]; then
  source "$LOCAL_CONFIG_FILE"
fi

if [ -f "$TOKEN_FILE" ]; then
  source "$TOKEN_FILE"
fi

if [ -z "${GRAMPS_API_TOKEN:-}" ]; then
  echo "No access token found; requesting a new token."
  "$ROOT_DIR/scripts/get_access_token.sh" "$TOKEN_FILE"
  if [ ! -f "$TOKEN_FILE" ]; then
    echo "ERROR: failed to retrieve access token"
    exit 1
  fi
  source "$TOKEN_FILE"
fi

PAGE_NAME="${1:-}"
PERSON_ID="${2:-}"
if [ -z "$PAGE_NAME" ]; then
  echo "Usage: $0 <page-name> [person-id]"
  exit 1
fi

PAGE_DIR="$PAGES_DIR/$PAGE_NAME"
if [ ! -d "$PAGE_DIR" ]; then
  echo "ERROR: page directory not found: $PAGE_DIR"
  exit 1
fi

SOURCE_FILE="$PAGE_DIR/source.txt"
if [ -z "$PERSON_ID" ]; then
  if [ ! -f "$SOURCE_FILE" ]; then
    echo "ERROR: source ID file not found: $SOURCE_FILE"
    exit 1
  fi
  PERSON_ID="$(tr -d '[:space:]' < "$SOURCE_FILE")"
fi

if [ -z "$PERSON_ID" ]; then
  echo "ERROR: person ID is empty"
  exit 1
fi

OUTPUT_DIR="$PAGE_DIR/output"
DATA_FILE="$OUTPUT_DIR/data.json"
ASSETS_DIR="$PAGE_DIR/assets"
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
  --person-id "$PERSON_ID" \
  --output "$DATA_FILE" \
  --assets-dir "$ASSETS_DIR"

echo "Loaded GRAMPS data for page '$PAGE_NAME' into $DATA_FILE"
