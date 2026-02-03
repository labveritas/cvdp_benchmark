"""Compatibility shim for cocotb_tools package."""

from .runner import get_runner  # re-export for convenience

__all__ = ["get_runner"]
