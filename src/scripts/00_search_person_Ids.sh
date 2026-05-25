#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/gramps_api.env"
LOCAL_CONFIG_FILE="$SCRIPT_DIR/gramps_api.local.env"
TOKEN_FILE="$SCRIPT_DIR/gramps_api_token.env"
PYTHON_SCRIPT="$SCRIPT_DIR/00_search_person_Ids.py"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: GRAMPS API config not found: $CONFIG_FILE"
  exit 1
fi

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <GrampsID>"
  exit 1
fi

PERSON_ID="$1"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to query the GRAMPS API"
  exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
  echo "ERROR: helper script not found: $PYTHON_SCRIPT"
  exit 1
fi

# Always refresh the access token before querying.
"$SCRIPT_DIR/01_get_access_token.sh" "$TOKEN_FILE"

if [ ! -f "$TOKEN_FILE" ]; then
  echo "ERROR: access token file not found: $TOKEN_FILE"
  exit 1
fi

source "$CONFIG_FILE"
if [ -f "$LOCAL_CONFIG_FILE" ]; then
  source "$LOCAL_CONFIG_FILE"
fi
source "$TOKEN_FILE"

if [ -z "${GRAMPS_API_TOKEN:-}" ]; then
  echo "ERROR: GRAMPS_API_TOKEN is empty after requesting token"
  exit 1
fi

export GRAMPS_API_BASE_URL
export GRAMPS_API_TOKEN
export GRAMPS_API_PERSON_SEARCH_PATH
export GRAMPS_API_PERSON_QUERY_PARAM
export GRAMPS_API_EVENT_DETAIL_PATH
export GRAMPS_API_MEDIA_SEARCH_PATH
export GRAMPS_API_MEDIA_QUERY_PARAM
export GRAMPS_API_NOTE_SEARCH_PATH
export GRAMPS_API_NOTE_QUERY_PARAM
export GRAMPS_API_TIMEOUT

python3 "$PYTHON_SCRIPT" "$PERSON_ID"
