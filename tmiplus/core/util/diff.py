from __future__ import annotations
from typing import Any, Dict, Tuple

def dict_diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    keys = set(old.keys()) | set(new.keys())
    diff = {}
    for k in keys:
        ov = old.get(k, None)
        nv = new.get(k, None)
        if ov != nv:
            diff[k] = (ov, nv)
    return diff
