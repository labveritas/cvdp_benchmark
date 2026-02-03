"""Compat shim for cocotb_tools.runner on cocotb<2.x environments."""

import re

try:
    from cocotb.runner import get_runner as _get_runner
except Exception:  # pragma: no cover - fallback when cocotb isn't present
    _get_runner = None

_UNIT_ORDER = ["s", "ms", "us", "ns", "ps", "fs"]
_UNIT_TO_FS = {
    "s": 10**15,
    "ms": 10**12,
    "us": 10**9,
    "ns": 10**6,
    "ps": 10**3,
    "fs": 1,
}


def _parse_time(value):
    match = re.match(r"^\\s*(\\d+)\\s*([a-zA-Z]+)\\s*$", str(value))
    if not match:
        return None
    num = int(match.group(1))
    unit = match.group(2).lower()
    if unit not in _UNIT_TO_FS:
        return None
    return num, unit


def _to_fs(parsed):
    num, unit = parsed
    return num * _UNIT_TO_FS[unit]


def _smaller_unit(unit):
    try:
        idx = _UNIT_ORDER.index(unit)
    except ValueError:
        return None
    if idx + 1 >= len(_UNIT_ORDER):
        return None
    return _UNIT_ORDER[idx + 1]


def _normalize_timescale(timescale):
    if not isinstance(timescale, (tuple, list)) or len(timescale) != 2:
        return timescale
    unit, precision = timescale
    unit_parsed = _parse_time(unit)
    prec_parsed = _parse_time(precision)
    if not unit_parsed or not prec_parsed:
        return timescale
    if _to_fs(prec_parsed) < _to_fs(unit_parsed):
        return timescale
    smaller = _smaller_unit(unit_parsed[1])
    if not smaller:
        return timescale
    return (unit, f"1{smaller}")


class _RunnerWrapper:
    def __init__(self, runner):
        self._runner = runner

    def build(self, *args, **kwargs):
        if "timescale" in kwargs and kwargs["timescale"] is not None:
            kwargs["timescale"] = _normalize_timescale(kwargs["timescale"])
        return self._runner.build(*args, **kwargs)

    def test(self, *args, **kwargs):
        return self._runner.test(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._runner, name)


def get_runner(sim=None):
    if _get_runner is None:
        raise ImportError("cocotb.runner.get_runner is unavailable")
    return _RunnerWrapper(_get_runner(sim))


__all__ = ["get_runner"]
