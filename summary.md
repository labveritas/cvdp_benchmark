# Comprehensive Verilog Design Problems (CVDP) - Paper Summary

## TL;DR
CVDP is a large, human-authored benchmark for Verilog RTL design and verification that targets both single-turn LLMs and tool-using agents. It contains 783 problems across 13 categories and evaluates RTL generation, verification, debugging, and comprehension. State-of-the-art models top out at about 34% pass@1 on code generation, with especially poor performance on verification tasks such as testbench and assertion generation. The paper contributes a dataset, evaluation infrastructure, and a detailed failure analysis framework that highlights gaps in current model capabilities.

## Motivation and Contributions
- Existing Verilog benchmarks are narrow, often saturated, and do not reflect full hardware workflows.
- CVDP expands task coverage, adds agentic formats, and introduces more realistic, challenging prompts.
- Four key contributions:
  1) First agentic-oriented Verilog benchmark with Dockerized tool use.
  2) Broader coverage of design and verification tasks.
  3) Higher difficulty with substantial headroom for progress.
  4) Failure analysis that identifies capability gaps in current models.

## Dataset Overview
- 783 problems across 13 categories.
- Authored by ~35 hardware engineers with 4+ years of Verilog/verification experience.
- Problems exist in two formats:
  - Non-Agentic (single-turn, full prompt/context provided).
  - Agentic (multi-turn, tool-using; runs inside Docker).
- Each datapoint is a small multi-file repository evaluated by a test harness (typically Cocotb).
- Models see the testbench context when relevant, but never see the test harness or the reference solution.
- Packaged as two JSONL files (Non-Agentic and Agentic).

## Task Categories (13 total)
**Code Generation**
- cid02: RTL code completion.
- cid03: Natural language spec to RTL.
- cid04: RTL code modification from spec.
- cid05: Spec to RTL with module instantiation and component reuse (Agentic).
- cid07: RTL improvement (linting or QoR).
- cid12: Testbench stimulus generation.
- cid13: Testbench checker generation.
- cid14: Assertion generation.
- cid16: RTL debugging and bug fixing.

**Code Comprehension**
- cid06: RTL to/from specification correspondence.
- cid08: Testbench to/from test plan correspondence.
- cid09: RTL question answering.
- cid10: Testbench question answering.

Notes:
- Non-Agentic tasks are easy/medium; Agentic tasks include hard difficulty.
- All problems use an oracle context (minimal relevant files), not full-repo retrieval.

## Data Quality and Filtering
- 1,313 initial problems written; 783 retained after quality filtering.
- Two-stage filtering:
  1) Sanity checks (reference passes harness; initial context fails).
  2) LLM-based judging on ambiguity, consistency, category match, and behavioral match.
- Filtering threshold: aggregate score >= 8.0.
- Design verification categories saw the most filtering, yet still remained difficult.

## Benchmark Infrastructure
- Python-based evaluation with callbacks for custom models/agents.
- Runs inside Docker to isolate tools and artifacts.
- Open-source tools used where possible:
  - Icarus Verilog (simulation)
  - Yosys (synthesis)
  - Verilator (linting)
- Some verification tasks require commercial tools (Cadence Xcelium).
- Includes a "map" feature for batch evaluation and LLM-based datapoint filtering.
- Agentic and Non-Agentic formats can be converted for flexible evaluation.

## Evaluation Metrics
- Code Generation: pass@1 with n = 5 samples.
- Code Comprehension:
  - Correspondence tasks (cid06, cid08): BLEU.
  - Q&A tasks (cid09, cid10): LLM-based judging (scored by GPT o4-mini).

## Main Results
- Highest aggregate pass@1 on code generation: ~34% (Claude 3.7 Sonnet).
- GPT-4.1 ~29%, Llama 3.1 405B ~23%.
- Agentic tasks are harder when evaluated as single-turn prompts:
  - GPT-4.1 drops to ~21% (about 8 points lower than Non-Agentic).
  - Claude 3.7 Sonnet drops about 4 points.
  - Llama 3.1 405B drops about 2 points.
- Design verification (testbench stimulus/checker, assertions) has much lower pass rates than RTL generation tasks.
- Q&A comprehension tasks are relatively easy for most LLMs, suggesting maturity in conversational QA but raising questions about technical reliability.

## Failure Analysis
- Pipeline:
  1) Use a reasoning LLM to reflect on failures.
  2) Embed reflections and cluster with k-means (silhouette-based selection).
  3) Use a reasoning LLM to summarize cluster-level failure modes.
- Key findings:
  - Verification tasks (cid12-14) show more diverse and numerous failure clusters than RTL coding.
  - Failure entities include syntax/functional errors, misplaced SVA, and insufficient coverage.
  - Quality filtering reduces ambiguity and cluster count but does not close the gap for verification tasks.

## Case Studies (Appendix A)
- Brick sort RTL example: errors in blocking vs non-blocking usage, bounds checking, and cycle-accurate timing (extra cycle per pass).
- Bit-width handling: failing to explicitly zero-extend 4-bit operands to an 8-bit output, causing silent specification violations.

## Limitations
- Agentic contexts are larger but still oracle-only; no full-repo retrieval.
- Q&A comprehension tasks are not sufficiently challenging.
- Benchmark does not cover the full end-to-end hardware lifecycle from project inception to fabrication.

## Compute Requirements (Appendix C)
- Evaluation VM: 12 vCPUs, 24 GB RAM, Rocky Linux 8.10.
- Disk usage per model run: ~6.4 to 15 GB, often due to excessive logs or VCDs.
- Disk monitor aborts runs if a directory exceeds 100 MB; supports compression.

## Overall Takeaway
CVDP is a substantial step forward for evaluating LLMs and agents in RTL design and verification. It exposes clear weaknesses in verification and component reuse tasks, provides infrastructure for realistic tool interaction, and sets a higher bar for future research in AI-driven hardware design.
