# CVDP Agentic Record Structure (System Message, Prompt, Context, Patch, Harness)

This note summarizes the typical *skeleton* of fields in the agentic JSONL records of the CVDP dataset.

## Record-Level Fields (Agentic JSONL)
Each JSONL line is one problem with fields like:
- `id`: unique sample id
- `categories`: list like `["cid013", "medium"]`
- `system_message`: tool instructions + workflow constraints
- `prompt`: task description
- `context`: files the agent can read (path -> content)
- `patch`: files the agent is expected to edit (path -> initial content)
- `harness`: evaluation files (path -> content)

## system_message: Common Skeleton
Typical sections found across samples:
1) **Tool availability list**
   - Directory listing (`ls`, `tree`)
   - Read files (`cat <filename>`)
   - Write files (`echo <content> > <filename>`)
   - Compile Verilog (`iverilog -o ... -g2012 ...`)
   - Run simulation (`vvp <output>.out`)
   - Sometimes: update file content with `sed -i ...`
   - Often: `pwd`

2) **Task framing**
   - “You will be given a prompt and your task is to understand it and solve the issue…”
   - Mentions producing a Linux patch at the end.

3) **Reasoning workflow requirement**
   - Step-by-step format: `thought`, `action`, `observation`.

4) **Final output format**
   - Final step must include a summary and a `patch` section.
   - Patch is a Linux diff/patch.
   - Constraint: patch applies to **a single file**.

### system_message: Template (approximate)
```text
You are a language model that has the following file operations available at your disposal:
  - List files: ls, tree
  - Read files: cat <filename>
  - Write files: echo <content> > <filename>
  - Compile Verilog: iverilog -o <out>.out -g2012 <verilog> <testbench>
  - Run simulation: vvp <out>.out
  - (optional) Update file: sed -i '...'
  - (often) pwd

You will be given a prompt and your task is to solve the issue using the commands above.
At the end, create a Linux patch highlighting the necessary file updates.

Use the following approach:
  - thought
  - action
  - observation

Final output format:
  - thought (summary + intro to the patch)
  - patch (Linux patch)

The patch should only be applied to a single file.
```

## prompt: Common Skeleton
The `prompt` is the actual task description. Typical structure:
- **High-level goal** (e.g., implement module, modify RTL, add checker logic).
- **References to spec docs** in `context` (e.g., `docs/specification.md`).
- **Target file path** that must be created or edited (often in `rtl/` or `verif/`).
- **Explicit requirements** in bullets: functionality, interface, edge cases, timing.
- **Constraints** (e.g., must pass given testbench, must keep certain signals).
- **Notes about existing modules** to reuse/instantiate.

### prompt: Template (approximate)
```text
Task summary paragraph (what to build or modify)

References:
- Specification: <path in context>
- Existing RTL/testbench files: <paths>

Requirements:
- Functional behavior: ...
- Interface signals / timing: ...
- Coverage or edge cases: ...

Deliverable:
- Edit or create <target file path>
```

## context: Common Structure
- `context` is a JSON object: **file path -> file content**.
- Contains only the files the agent is allowed to read.
- Examples: specification docs, RTL modules, testbench files.

## patch: Common Structure
- `patch` is a JSON object: **file path -> file content**.
- Typically indicates the file the agent should modify or generate.
- The system message requires the final patch to touch **only one file**.

## harness: Common Structure
- `harness` is a JSON object: **file path -> file content**.
- Used for evaluation only (simulation/test runners, docker configs, env).
- Typical paths: `docker-compose.yml`, `src/test_runner.py`, `src/*.sv`.
- Not intended for editing by the agent.

## Notes
- Variations exist between samples (e.g., presence of `sed -i` in tool list), but the overall skeleton is consistent.
- Agentic problems often require integrating multiple existing modules or adding verification/checker logic.

## Example Excerpt (cid014, agentic)
Below is a short excerpt from a cid014 sample (assertion generation). Truncated for readability.

```text
id: cvdp_agentic_AES_encryption_decryption_0020
categories: ["cid014", "medium"]

system_message (snippet):
You are a language model that has the following file operations available at your disposal:
  - List files: ls, tree
  - Read files: cat <filename>
  - Write files: echo <content> > <filename>
  - Compile Verilog: iverilog -o <out>.out -g2012 <verilog> <testbench>
  - Run simulation: vvp <out>.out
  - ...

prompt (snippet):
I have a hierarchical AES encryption design with 3 main modules:
- aes_enc_top
- aes_encrypt
- sbox
These modules are located in the rtl directory. Please enhance the design
by adding SystemVerilog Assertions (SVA) to verify control logic, functional
behavior, round sequencing, and mode-dependent correctness.
...

context files:
- rtl/aes_enc_top.sv
- rtl/aes_encrypt.sv
- rtl/sbox.sv

patch files:
- rtl/aes_enc_top.sv
- rtl/aes_encrypt.sv

harness files:
- Dockerfile
- docker-compose.yml
- src/harness_library.py
- src/test_aes_enc_top.py
- src/test_runner.py
```
