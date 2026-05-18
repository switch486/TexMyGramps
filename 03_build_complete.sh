#!/usr/bin/env zsh

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
 