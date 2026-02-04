"""Site customizations for cocotb runner compatibility."""

from __future__ import annotations

import builtins

try:
    import cocotb.runner as _cocotb_runner
    from cocotb_tools import runner as _shim_runner

    _cocotb_runner.get_runner = _shim_runner.get_runner
except Exception:
    # Best-effort patching only
    pass


def cvdp_to_unsigned(value):
    """Best-effort unsigned integer conversion for cocotb values."""
    try:
        return value.to_unsigned()
    except Exception:
        pass
    try:
        return value.integer
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        return value


def cvdp_to_signed(value):
    """Best-effort signed integer conversion for cocotb values."""
    try:
        return value.to_signed()
    except Exception:
        pass
    try:
        return value.signed_integer
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        return value


# Expose helpers so rewritten tests can call them without imports.
builtins.cvdp_to_unsigned = cvdp_to_unsigned
builtins.cvdp_to_signed = cvdp_to_signed

# Add missing BinaryValue APIs if needed (cocotb<2.x)
try:
    from cocotb.binary import BinaryValue

    if not hasattr(BinaryValue, "to_unsigned"):
        BinaryValue.to_unsigned = lambda self: self.integer
    if not hasattr(BinaryValue, "to_signed"):
        BinaryValue.to_signed = lambda self: self.signed_integer
except Exception:
    pass
