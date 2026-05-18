#!/usr/bin/env bash

# master_generate.sh
#
# Runs:
#   1. ./src/scripts/01_get_access_token.sh
#   2. ./02_load_data.sh <pageName> for every page* directory
#
# Features:
# - sequential execution
# - continues on page failures
# - child script output redirected to log files
# - concise console progress output
# - logs executed command + working directory
# - failed pages stored for manual retry
#
# Usage:
#   chmod +x master_generate.sh
#   ./master_generate.sh

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STAGE="${1:-}"
if [[ "$#" -gt 1 ]]; then
    echo "Usage: $0 [stage]"
    exit 1
fi

PAGES_DIR="$ROOT_DIR/src/pages${STAGE:+_$STAGE}"
SCRIPT_DIR="$ROOT_DIR/src/scripts"
GEN_SCRIPT="./02_load_data.sh"

LOG_DIR="$ROOT_DIR/logs"
MASTER_LOG="$LOG_DIR/master_load.log"
FAILED_FILE="$LOG_DIR/failed_pages.log"

mkdir -p "$LOG_DIR"

# reset per-run files
: > "$FAILED_FILE"
: > "$MASTER_LOG"

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    local message="$1"

    echo "[$(timestamp)] $message" | tee -a "$MASTER_LOG"
}

log "========================================"
log "Generation started"

# sanity checks
if [[ ! -d "$SCRIPT_DIR" ]]; then
    log "ERROR: Script directory not found: $SCRIPT_DIR"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/02_load_data.sh" ]]; then
    log "ERROR: Missing script: $SCRIPT_DIR/02_load_data.sh"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/01_get_access_token.sh" ]]; then
    log "ERROR: Missing script: $SCRIPT_DIR/01_get_access_token.sh"
    exit 1
fi

if [[ ! -d "$PAGES_DIR" ]]; then
    log "ERROR: Pages directory not found: $PAGES_DIR"
    exit 1
fi

#
# PRE-LOAD STEP
#

log "----------------------------------------"
log "START access token generation"

PRE_COMMAND="./src/scripts/01_get_access_token.sh"
PRE_LOG="$LOG_DIR/01_get_access_token.log"

log "WORKDIR: $ROOT_DIR"
log "COMMAND: $PRE_COMMAND"
log "OUTPUT LOG: $PRE_LOG"

{
    echo "========================================"
    echo "RUN START : $(timestamp)"
    echo "WORKDIR   : $ROOT_DIR"
    echo "COMMAND   : $PRE_COMMAND"
    echo "========================================"
} >> "$PRE_LOG"

$PRE_COMMAND >> "$PRE_LOG" 2>&1

PRE_EXIT_CODE=$?

echo "" >> "$PRE_LOG"
echo "EXIT CODE : $PRE_EXIT_CODE" >> "$PRE_LOG"
echo "RUN END   : $(timestamp)" >> "$PRE_LOG"
echo "" >> "$PRE_LOG"

if [[ "$PRE_EXIT_CODE" -eq 0 ]]; then
    log "SUCCESS access token generation"
else
    log "FAILED access token generation (exit code: $PRE_EXIT_CODE)"
    log "Stopping execution"

    exit 1
fi

#
# PAGE LOAD
#

TOTAL=0
SUCCESS=0
FAILED=0

while IFS= read -r -d '' dir; do
    PAGE_NAME="$(basename "$dir")"

    TOTAL=$((TOTAL + 1))

    PAGE_LOG="$LOG_DIR/${PAGE_NAME}.log"

    if [[ -n "$STAGE" ]]; then
        COMMAND="$GEN_SCRIPT $PAGE_NAME $STAGE"
    else
        COMMAND="$GEN_SCRIPT $PAGE_NAME"
    fi

    log "----------------------------------------"
    log "START [$TOTAL] $PAGE_NAME"
    log "WORKDIR: $SCRIPT_DIR"
    log "COMMAND: $COMMAND"
    log "OUTPUT LOG: $PAGE_LOG"

    {
        echo "========================================"
        echo "RUN START : $(timestamp)"
        echo "WORKDIR   : $SCRIPT_DIR"
        echo "COMMAND   : $COMMAND"
        echo "========================================"
    } >> "$PAGE_LOG"

    (
        cd "$SCRIPT_DIR" || exit 1

        $COMMAND
    ) >> "$PAGE_LOG" 2>&1

    EXIT_CODE=$?

    echo "" >> "$PAGE_LOG"
    echo "EXIT CODE : $EXIT_CODE" >> "$PAGE_LOG"
    echo "RUN END   : $(timestamp)" >> "$PAGE_LOG"
    echo "" >> "$PAGE_LOG"

    if [[ "$EXIT_CODE" -eq 0 ]]; then
        SUCCESS=$((SUCCESS + 1))
        log "SUCCESS [$TOTAL] $PAGE_NAME"
    else
        FAILED=$((FAILED + 1))

        log "FAILED  [$TOTAL] $PAGE_NAME (exit code: $EXIT_CODE)"

        echo "$PAGE_NAME" >> "$FAILED_FILE"
    fi

done < <(
    find "$PAGES_DIR" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
        -name 'page*' \
        -print0 | sort -z
)

#
# SUMMARY
#

log "----------------------------------------"
log "Generation finished"
log "Total   : $TOTAL"
log "Success : $SUCCESS"
log "Failed  : $FAILED"

if [[ "$FAILED" -gt 0 ]]; then
    log "Failed pages saved to:"
    log "$FAILED_FILE"

    log "Manual retry example:"
    log "cd $SCRIPT_DIR && ./02_load_data.sh <pageName>"
fi

log "========================================"