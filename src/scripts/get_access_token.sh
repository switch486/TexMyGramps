#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/gramps_api.env"
OUTPUT_FILE="${1:-$SCRIPT_DIR/gramps_api_token.env}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: GRAMPS API config not found: $CONFIG_FILE"
  exit 1
fi

source "$CONFIG_FILE"

if [ -z "${GRAMPS_API_BASE_URL:-}" ]; then
  echo "ERROR: GRAMPS_API_BASE_URL is not set in $CONFIG_FILE"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to request a new access token"
  exit 1
fi

if [ -n "${GRAMPS_API_USER:-}" ] && [ -n "${GRAMPS_API_PASSWORD:-}" ]; then
  URL="${GRAMPS_API_BASE_URL%/}/token"
  LOGIN_METHOD="username/password"
  PAYLOAD_TYPE="credentials"
elif [ -n "${GRAMPS_API_REFRESH_TOKEN:-}" ]; then
  URL="${GRAMPS_API_BASE_URL%/}/token/refresh"
  LOGIN_METHOD="refresh token"
  PAYLOAD_TYPE="refresh"
else
  echo "ERROR: GRAMPS_API_USER and GRAMPS_API_PASSWORD are not both set, and no GRAMPS_API_REFRESH_TOKEN is configured."
  exit 1
fi

echo "Requesting access token via $LOGIN_METHOD from: $URL"
ACCESS_TOKEN=$(python3 - "$URL" "${GRAMPS_API_USER:-}" "${GRAMPS_API_PASSWORD:-}" "${GRAMPS_API_REFRESH_TOKEN:-}" "$PAYLOAD_TYPE" <<'PY'
import json
import sys
import requests

url, username, password, refresh_token, payload_type = sys.argv[1:6]
headers = {"Content-Type": "application/json"}
if payload_type == "credentials":
    payload = {"username": username, "password": password}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
elif payload_type == "refresh":
    resp = requests.post(url, headers={"Authorization": f"Bearer {refresh_token}", "Content-Type": "application/json"}, timeout=30)
else:
    raise SystemExit("ERROR: Unsupported payload type")

try:
    resp.raise_for_status()
except requests.exceptions.RequestException as exc:
    raise SystemExit(f"ERROR: Failed to request token: {exc}\nResponse: {resp.text}")

data = resp.json()
if "accessToken" in data:
    print(data["accessToken"])
elif "access_token" in data:
    print(data["access_token"])
else:
    raise SystemExit("ERROR: No access token returned from GRAMPS")
PY
)

echo "GRAMPS_API_TOKEN=$ACCESS_TOKEN" > "$OUTPUT_FILE"
chmod 600 "$OUTPUT_FILE"
echo "Wrote access token to: $OUTPUT_FILE"
