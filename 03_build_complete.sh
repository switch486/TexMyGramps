#!/usr/bin/env zsh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment variables from .env files
# Try multiple common filenames so we pick up MAPBOX_TOKEN and other config
for env_file in "$ROOT_DIR/src/scripts/gramps_api.local.env" "$ROOT_DIR/src/scripts/gramps_api_token.env"; do
    if [[ -f "$env_file" ]]; then
        echo "[ENV] Loading environment from: $env_file"
        set +u
        set -a
        source "$env_file"
        set +a
        set -u
    fi
done

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
 