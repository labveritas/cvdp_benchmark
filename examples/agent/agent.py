#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Simple CVDP agent implementation for the agentic workflow.
This agent reads prompt.json and makes changes to files in the mounted directories.
"""

import os
import json
import sys
import time
import datetime
import re
import tempfile
import subprocess
from typing import List, Optional

from google import genai
try:
    from google.genai import types  # Optional, for system_instruction config
except Exception:
    types = None
from pydantic import BaseModel, Field

def read_prompt():
    """Read prompt data from prompt.json"""
    prompt_path = os.getenv("CVDP_PROMPT_JSON")
    if not prompt_path:
        code_dir = os.getenv("CVDP_CODE_DIR", "/code")
        prompt_path = os.path.join(code_dir, "prompt.json")
    try:
        with open(prompt_path, "r") as f:
            prompt_data = json.load(f)
            return {
                "prompt": prompt_data.get("prompt", ""),
                "system_message": prompt_data.get("system_message", "")
            }
    except Exception as e:
        print(f"Error reading prompt.json at {prompt_path}: {e}")
        return {"prompt": "", "system_message": ""}

def list_directory_files(dir_path):
    """List all files in a directory recursively"""
    files = []
    if os.path.exists(dir_path):
        for root, _, filenames in os.walk(dir_path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, dir_path)
                files.append(rel_path)
    return files

def read_file(file_path):
    """Read the contents of a file"""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return ""

def write_file(file_path, content):
    """Write content to a file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Successfully wrote to {file_path}")
    except Exception as e:
        print(f"Error writing to file {file_path}: {e}")

class FileChange(BaseModel):
    path: str = Field(..., description="Relative path under rtl/ to write")
    content: str = Field(..., description="Full file contents")


class AgentResponse(BaseModel):
    files: List[FileChange] = Field(default_factory=list)
    summary: Optional[str] = None


def _get_genai_client():
    api_key = os.getenv("GCP_API_KEY")
    if not api_key:
        raise RuntimeError("GCP_API_KEY is not set")
    return genai.Client(vertexai=True, api_key=api_key)


def _get_llm_log_path(code_dir: str) -> str:
    log_path = os.getenv("CVDP_LLM_LOG_PATH")
    if log_path:
        return log_path
    reports_dir = os.getenv("CVDP_REPORTS_DIR")
    if not reports_dir:
        issue_dir = os.getenv("CVDP_ISSUE_DIR")
        if issue_dir:
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(issue_dir)), "reports")
    if reports_dir:
        os.makedirs(reports_dir, exist_ok=True)
        issue_id = os.path.basename(os.getenv("CVDP_ISSUE_DIR", "")).strip() or "llm"
        return os.path.join(reports_dir, f"{issue_id}_llm_trace.jsonl")
    rundir = os.getenv("CVDP_RUNDIR_DIR", os.path.join(code_dir, "rundir"))
    os.makedirs(rundir, exist_ok=True)
    return os.path.join(rundir, "llm_trace.jsonl")


def _serialize_response(response):
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump()
        except Exception:
            pass
    if hasattr(response, "to_dict"):
        try:
            return response.to_dict()
        except Exception:
            pass
    try:
        return response.__dict__
    except Exception:
        return {"repr": repr(response)}

def _json_safe(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _extract_tool_calls(response):
    tool_calls = []
    try:
        candidates = getattr(response, "candidates", []) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", []) if content is not None else []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    try:
                        tool_calls.append(fc.to_dict())
                    except Exception:
                        tool_calls.append({"name": getattr(fc, "name", None), "args": getattr(fc, "args", None)})
    except Exception:
        pass
    return tool_calls


def _log_llm_step(code_dir: str, step: dict) -> None:
    log_path = _get_llm_log_path(code_dir)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(_json_safe(step), ensure_ascii=False) + "\n")


def _extract_json(text: str) -> Optional[str]:
    if not text:
        return None
    if "```" in text:
        # Try to extract fenced JSON block
        start = text.find("```json")
        if start != -1:
            start = text.find("\n", start) + 1
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()
    return None

def _extract_patch(text: str) -> Optional[str]:
    if not text:
        return None
    for fence in ("```diff", "```patch", "```"):
        start = text.find(fence)
        if start != -1:
            start = text.find("\n", start) + 1
            end = text.find("```", start)
            if end != -1:
                snippet = text[start:end].strip()
                if snippet.startswith("--- "):
                    return snippet
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- "):
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith("+++ "):
                    start = i
                    break
            if start is not None:
                break
    if start is None:
        return None
    end = len(lines)
    diff_prefixes = ("diff ", "--- ", "+++ ", "@@ ", "+", "-", " ", "\\ No newline")
    while end > start and not lines[end - 1].startswith(diff_prefixes):
        end -= 1
    patch_text = "\n".join(lines[start:end]).strip()
    return patch_text or None


def _sanitize_patch(patch_text: str) -> str:
    allowed_prefixes = ("diff ", "index ", "--- ", "+++ ", "@@ ", "+", "-", " ", "\\ No newline")
    lines = patch_text.splitlines()
    # Drop any leading non-diff chatter
    start = 0
    for i, line in enumerate(lines):
        if line.startswith(("diff ", "--- ")):
            start = i
            break
    cleaned = []
    for line in lines[start:]:
        if line.startswith("```"):
            continue
        if line.startswith(allowed_prefixes):
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _apply_patch(code_dir: str, patch_text: str) -> None:
    patch_text = _sanitize_patch(patch_text)
    if not patch_text:
        raise RuntimeError("patch sanitized to empty")
    strip = 1 if re.search(r'^[+-]{3} [ab]/', patch_text, re.M) else 0
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write(patch_text)
        patch_path = f.name
    try:
        result = subprocess.run(
            ["patch", f"-p{strip}", "-i", patch_path, "--batch", "--silent"],
            cwd=code_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "patch failed")
    finally:
        try:
            os.unlink(patch_path)
        except Exception:
            pass


def _get_response_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    parts = []
    try:
        candidates = getattr(response, "candidates", []) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            cand_parts = getattr(content, "parts", []) if content is not None else []
            for part in cand_parts:
                t = getattr(part, "text", None)
                if t:
                    parts.append(t)
    except Exception:
        pass
    return "\n".join(parts)


def _call_llm(prompt: str, system_message: str, rtl_files: List[str], code_dir: str) -> AgentResponse:
    model = os.getenv("CVDP_LLM_MODEL", "gemini-3-flash-preview")
    client = _get_genai_client()

    system_msg = system_message or ""
    user_msg = prompt or ""

    config = None
    if types and system_msg:
        try:
            config = types.GenerateContentConfig(system_instruction=system_msg)
        except Exception:
            config = None

    if config:
        contents = [user_msg]
    elif system_msg:
        contents = [system_msg, user_msg]
    else:
        contents = [user_msg]

    try:
        if config:
            response = client.models.generate_content(model=model, contents=contents, config=config)
        else:
            response = client.models.generate_content(model=model, contents=contents)
        text = _get_response_text(response)
        _log_llm_step(code_dir, {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "model": model,
            "system_message": system_msg,
            "user_prompt": user_msg,
            "tool_calls": _extract_tool_calls(response),
            "response_text": text,
            "response_raw": _serialize_response(response),
        })
        json_text = _extract_json(text)
        if json_text:
            try:
                data = json.loads(json_text)
                return AgentResponse(**data)
            except Exception as e:
                patch_text = _extract_patch(text)
                if patch_text:
                    try:
                        _apply_patch(code_dir, patch_text)
                        return AgentResponse(files=[], summary=None)
                    except Exception as patch_error:
                        return AgentResponse(files=[], summary=f"ERROR: {patch_error}")
                return AgentResponse(files=[], summary=f"ERROR: {e}")
        patch_text = _extract_patch(text)
        if patch_text:
            try:
                _apply_patch(code_dir, patch_text)
                return AgentResponse(files=[], summary=None)
            except Exception as patch_error:
                return AgentResponse(files=[], summary=f"ERROR: {patch_error}")
        return AgentResponse(files=[], summary="ERROR: Failed to parse model response")
    except Exception as e:
        return AgentResponse(files=[], summary=f"ERROR: {e}")


def run_agent(prompt, system_message):
    """Run the LLM and apply returned file changes."""
    code_dir = os.getenv("CVDP_CODE_DIR", "/code")

    rtl_files = list_directory_files(os.path.join(code_dir, "rtl"))

    response = _call_llm(prompt, system_message, rtl_files, code_dir)

    # Apply file updates
    for change in response.files:
        rel_path = change.path.strip().lstrip("/")
        if not rel_path.startswith("rtl/"):
            print(f"Skipping non-RTL path: {rel_path}")
            continue
        target_path = os.path.join(code_dir, rel_path)
        write_file(target_path, change.content)
        print(f"Updated {rel_path}")

    # Write a simple report
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    rundir = os.getenv("CVDP_RUNDIR_DIR", os.path.join(code_dir, "rundir"))
    write_file(os.path.join(rundir, "agent_executed.txt"), f"Agent executed at {timestamp}\nPrompt: {prompt}\n")
    if response.summary:
        write_file(os.path.join(code_dir, "docs", "agent_report.md"), response.summary)

def main():
    """Main agent function"""
    print("Starting CVDP agent...")
    
    # Read the prompt
    prompt_data = read_prompt()
    prompt = prompt_data.get("prompt", "")
    system_message = prompt_data.get("system_message", "")
    if not prompt:
        print("No prompt found in prompt.json. Exiting.")
        sys.exit(1)
    
    # Process the prompt and modify files
    run_agent(prompt, system_message)
    
    print("Agent execution completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main() 
