# Cocotb Compatibility Notes

## Summary
This note records the cocotb compatibility fixes applied to local (non‑docker) harnesses and the datapoints affected.

## Code Changes
1) `shims/sitecustomize.py`
- Added `cvdp_to_unsigned()` and `cvdp_to_signed()` helpers.
- Injected helpers into `builtins` so tests can call them without extra imports.
- Backfilled `BinaryValue.to_unsigned` and `BinaryValue.to_signed` when missing (cocotb < 2.x).
- Kept existing `cocotb.runner.get_runner` shim.

2) `tools/build_local_dataset.py`
- Rewrites cocotb API usage in harness `*.py` files when generating local datasets:
  - `X.to_signed()` -> `cvdp_to_signed(X)`
  - `X.to_unsigned()` -> `cvdp_to_unsigned(X)`
  - `X.integer` -> `cvdp_to_unsigned(X)`
- This prevents failures such as:
  - `BinaryValue.to_signed` missing
  - `int` object has no attribute `integer`

## Datasets Regenerated
Local (non‑commercial, agentic) datasets regenerated with the new rewrites:
- `cvdp-benchmark-dataset/by_cid/cid003/cvdp_v1.0.2_agentic_code_generation_no_commercial_local.jsonl`
- `cvdp-benchmark-dataset/by_cid/cid004/cvdp_v1.0.2_agentic_code_generation_no_commercial_local.jsonl`
- `cvdp-benchmark-dataset/by_cid/cid005/cvdp_v1.0.2_agentic_code_generation_no_commercial_local.jsonl`

## Datapoints Explicitly Affected (API Errors Observed)
These datapoints previously failed due to the cocotb API mismatches that the rewrite targets:

### api_to_signed (BinaryValue.to_signed missing)
- `cvdp_agentic_phase_rotation_0013` (cid004)
- `cvdp_agentic_phase_rotation_0031` (cid004)
- `cvdp_agentic_phase_rotation_0028` (cid005)

### api_int_integer (int.integer misuse)
- `cvdp_agentic_AES_encryption_decryption_0018` (cid005)
- `cvdp_agentic_event_storing_0001` (cid005)

## Regeneration Command (if needed)
```bash
./.venv/bin/python tools/build_local_dataset.py \
  -i cvdp-benchmark-dataset/by_cid/cidXXX/cvdp_v1.0.2_agentic_code_generation_no_commercial.jsonl \
  -o cvdp-benchmark-dataset/by_cid/cidXXX/cvdp_v1.0.2_agentic_code_generation_no_commercial_local.jsonl \
  --shim-root shims
```

## Verification (optional)
```bash
rg -n "\\.to_signed\\(\\)|\\.to_unsigned\\(\\)|\\.integer" \
  -S cvdp-benchmark-dataset/by_cid/cidXXX/cvdp_v1.0.2_agentic_code_generation_no_commercial_local.jsonl
```
