#!/usr/bin/env python3
"""
Build a local-runner JSONL dataset from a base dataset by:
1) Injecting a local_harness.sh generated from docker-compose.yml
2) Injecting cocotb_tools compatibility shim into harness/src
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml


def _bash_single_quote(value: str) -> str:
    # Safe single-quote for bash: close, escape, reopen
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _normalize_command(cmd: Any) -> str:
    if cmd is None:
        return ""
    if isinstance(cmd, list):
        return " ".join(shlex.quote(str(x)) for x in cmd)
    cmd = str(cmd).strip()
    if not cmd:
        return ""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return cmd
    if len(tokens) >= 3 and tokens[0].endswith("sh") and tokens[1] == "-c":
        return tokens[2]
    return cmd


def _extract_from_yaml(compose_text: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        data = yaml.safe_load(compose_text)
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return None, None
    for _name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        cmd = svc.get("command")
        wd = svc.get("working_dir")
        if cmd is not None:
            return cmd, wd
    return None, None


def _extract_from_text(compose_text: str) -> Tuple[Optional[str], Optional[str]]:
    cmd = None
    wd = None
    for line in compose_text.splitlines():
        if re.match(r"^\\s*command\\s*:", line):
            cmd = line.split(":", 1)[1].strip()
            cmd = cmd.strip().strip('"').strip("'")
        if re.match(r"^\\s*working_dir\\s*:", line):
            wd = line.split(":", 1)[1].strip()
            wd = wd.strip().strip('"').strip("'")
        if cmd and wd:
            break
    return cmd, wd


def _extract_command_and_workdir(compose_text: str) -> Tuple[str, Optional[str]]:
    cmd, wd = _extract_from_yaml(compose_text)
    if cmd is None:
        cmd, wd = _extract_from_text(compose_text)
    cmd = _normalize_command(cmd)
    if not cmd:
        cmd = "pytest -s -o cache_dir=/rundir/harness/.cache /src/test_runner.py -v"
    return cmd, wd


def _render_local_harness(command: str, working_dir: Optional[str]) -> str:
    cmd_quoted = _bash_single_quote(command)
    wd_quoted = _bash_single_quote(working_dir) if working_dir else "''"
    return f"""#!/bin/bash
set -euo pipefail
ISSUE_DIR="${{CVDP_ISSUE_DIR:-$(pwd)}}"
SRC_DIR="${{CVDP_SRC_DIR:-$ISSUE_DIR/src}}"
CODE_DIR="${{CVDP_CODE_DIR:-$ISSUE_DIR}}"
RUNDIR_DIR="${{CVDP_RUNDIR_DIR:-$ISSUE_DIR/rundir}}"
ENV_FILE="$SRC_DIR/.env"

if [ -n "${{CVDP_VENV_PYTHON:-}}" ]; then
  VENV_BIN="$(dirname "$CVDP_VENV_PYTHON")"
  export PATH="$VENV_BIN:$PATH"
fi

if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${{line%%#*}}"
    if [ -z "${{line// }}" ]; then
      continue
    fi
    if ! echo "$line" | grep -q "="; then
      continue
    fi
    key="${{line%%=*}}"
    value="${{line#*=}}"
    key="$(echo "$key" | xargs)"
    value="$(echo "$value" | xargs)"
    value="${{value//\\/code/$CODE_DIR}}"
    value="${{value//\\/src/$SRC_DIR}}"
    value="${{value//\\/rundir/$RUNDIR_DIR}}"
    export "$key=$value"
  done < "$ENV_FILE"
fi

if [ -n "${{PYTHONPATH:-}}" ]; then
  export PYTHONPATH="$PYTHONPATH:$SRC_DIR"
else
  export PYTHONPATH="$SRC_DIR"
fi

mkdir -p "$RUNDIR_DIR"
if [ "${{TOPLEVEL_LANG:-verilog}}" = "verilog" ] && [ -n "${{VERILOG_SOURCES:-}}" ]; then
  TS_FILE="$RUNDIR_DIR/cvdp_timescale.v"
  if [ ! -f "$TS_FILE" ]; then
    cat > "$TS_FILE" <<'EOF'
`timescale 1ns/1ps
module cvdp_timescale_dummy;
endmodule
EOF
  fi
  export VERILOG_SOURCES="$TS_FILE $VERILOG_SOURCES"
fi

CMD={cmd_quoted}
# Avoid double-substitution for /code/rundir paths
CMD="${{CMD//\\/code\\/rundir/$RUNDIR_DIR}}"
CMD="${{CMD//\\/code/$CODE_DIR}}"
CMD="${{CMD//\\/src/$SRC_DIR}}"
# Replace standalone /rundir tokens only
RUNDIR_ESC="$(printf '%s' "$RUNDIR_DIR" | sed -e 's/[\\/&]/\\\\&/g')"
CMD="$(printf '%s' "$CMD" | sed -E "s#(^|[[:space:]]|=)/rundir#\\1${{RUNDIR_ESC}}#g")"

WORKDIR={wd_quoted}
if [ -z "$WORKDIR" ]; then
  WORKDIR="$ISSUE_DIR"
fi
if [[ "$WORKDIR" == /code/rundir* ]]; then
  WORKDIR="$RUNDIR_DIR${{WORKDIR#/code/rundir}}"
elif [[ "$WORKDIR" == /code* ]]; then
  WORKDIR="$CODE_DIR${{WORKDIR#/code}}"
elif [[ "$WORKDIR" == /src* ]]; then
  WORKDIR="$SRC_DIR${{WORKDIR#/src}}"
elif [[ "$WORKDIR" == /rundir* ]]; then
  WORKDIR="$RUNDIR_DIR${{WORKDIR#/rundir}}"
fi

cd "$WORKDIR"
echo "Running harness: $CMD"
eval "$CMD"
"""


def _load_shim(shim_root: Path) -> Tuple[str, str, str]:
    init_path = shim_root / "cocotb_tools" / "__init__.py"
    runner_path = shim_root / "cocotb_tools" / "runner.py"
    sitecustomize_path = shim_root / "sitecustomize.py"
    return (
        init_path.read_text(encoding="utf-8"),
        runner_path.read_text(encoding="utf-8"),
        sitecustomize_path.read_text(encoding="utf-8"),
    )


def build_local_dataset(input_path: Path, output_path: Path, shim_root: Path) -> None:
    shim_init, shim_runner, shim_site = _load_shim(shim_root)

    with input_path.open("r", encoding="utf-8") as fin, output_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            obj = json.loads(line)
            harness = obj.get("harness")
            if not isinstance(harness, dict):
                ctx = obj.get("context", {})
                if isinstance(ctx, dict):
                    harness = ctx.get("harness")
            if isinstance(harness, dict):
                compose_text = harness.get("docker-compose.yml") or ""
                if compose_text:
                    cmd, wd = _extract_command_and_workdir(compose_text)
                    harness["local_harness.sh"] = _render_local_harness(cmd, wd)
                # Inject shim into harness src
                harness.setdefault("src/cocotb_tools/__init__.py", shim_init)
                harness.setdefault("src/cocotb_tools/runner.py", shim_runner)
                harness.setdefault("src/sitecustomize.py", shim_site)
            fout.write(json.dumps(obj, ensure_ascii=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local JSONL dataset")
    parser.add_argument("-i", "--input", required=True, help="Input JSONL dataset path")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL dataset path")
    parser.add_argument("--shim-root", default="shims", help="Shim root containing cocotb_tools")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    shim_root = Path(args.shim_root)
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    if not shim_root.exists():
        raise SystemExit(f"Shim root not found: {shim_root}")

    build_local_dataset(input_path, output_path, shim_root)


if __name__ == "__main__":
    main()
