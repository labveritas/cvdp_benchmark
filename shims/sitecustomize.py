"""Site customizations for cocotb runner compatibility."""

try:
    import cocotb.runner as _cocotb_runner
    from cocotb_tools import runner as _shim_runner

    _cocotb_runner.get_runner = _shim_runner.get_runner
except Exception:
    # Best-effort patching only
    pass
