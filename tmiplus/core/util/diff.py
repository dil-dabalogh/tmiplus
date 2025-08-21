from __future__ import annotations

from typing import Any


def dict_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    keys = set(old.keys()) | set(new.keys())
    diff = {}
    for k in keys:
        ov = old.get(k, None)
        nv = new.get(k, None)
        if ov != nv:
            diff[k] = (ov, nv)
    return diff
