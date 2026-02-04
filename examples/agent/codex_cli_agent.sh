#!/usr/bin/env bash
set -euo pipefail

PROMPT_JSON="${CVDP_PROMPT_JSON:-prompt.json}"
CODE_DIR="${CVDP_CODE_DIR:-$(pwd)}"
CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_ARGS="${CODEX_ARGS:-}"

if [ ! -f "$PROMPT_JSON" ]; then
  echo "prompt.json not found: $PROMPT_JSON" >&2
  exit 1
fi

# Feed ONLY the user prompt to Codex via stdin to preserve formatting.
python - <<'PY' | "$CODEX_BIN" -a never exec -s workspace-write -C "$CODE_DIR" --skip-git-repo-check $CODEX_ARGS -
import json
import os
import sys

path = os.environ.get("CVDP_PROMPT_JSON", "prompt.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
sys.stdout.write(data.get("prompt", ""))
PY
