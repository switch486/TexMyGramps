#!/usr/bin/env zsh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="$ROOT_DIR/src/scripts/gramps_api.env"
LOCAL_CONFIG_FILE="$ROOT_DIR/src/scripts/gramps_api.local.env"
TOKEN_FILE="$ROOT_DIR/src/scripts/gramps_api_token.env"

if [[ -x "$ROOT_DIR/src/scripts/01_get_access_token.sh" ]]; then
    echo "[ENV] Generating GRAMPS API token"
    "$ROOT_DIR/src/scripts/01_get_access_token.sh" "$TOKEN_FILE"
else
    echo "[ENV] Warning: token generation script not found: $ROOT_DIR/src/scripts/01_get_access_token.sh"
fi

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

export GRAMPS_API_BASE_URL \
  GRAMPS_API_TOKEN \
  GRAMPS_API_PERSON_QUERY_PARAM \
  GRAMPS_API_PERSON_SEARCH_PATH \
  GRAMPS_API_EVENT_DETAIL_PATH \
  GRAMPS_API_PLACE_DETAIL_PATH \
  GRAMPS_API_TIMEOUT

STAGE="${1:-}"
if [[ "$#" -gt 1 ]]; then
  echo "Usage: $0 [stage]"
  exit 1
fi

cd masterDocument
if [[ -n "$STAGE" ]]; then
  python3 build_complete.py "$STAGE"
else
  python3 build_complete.py
fi
 