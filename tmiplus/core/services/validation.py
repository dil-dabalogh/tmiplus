from __future__ import annotations
from typing import List, Tuple, Set, Dict
from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Member, Initiative, PTORecord, Assignment, Pool, State

def validate_references(adapter: DataAdapter, assignments: List[Assignment]) -> List[str]:
    errors: List[str] = []
    members = {m.name for m in adapter.list_members()}
    inits = {i.name for i in adapter.list_initiatives()}
    for a in assignments:
        if a.member_name not in members:
            errors.append(f"Unknown member: {a.member_name}")
        if a.initiative_name not in inits:
            errors.append(f"Unknown initiative: {a.initiative_name}")
    return errors

def allowed_pool_members(adapter: DataAdapter, init: Initiative) -> Set[str]:
    if not init.owner_pools:
        return {m.name for m in adapter.list_members() if m.active}
    allowed = set()
    for m in adapter.list_members():
        if not m.active:
            continue
        if m.pool in init.owner_pools:
            allowed.add(m.name)
    return allowed

def current_workload_index(assignments: List[Assignment]) -> Dict[Tuple[str, str], Assignment]:
    return {(a.member_name, a.week_start): a for a in assignments}

def is_done(init: Initiative) -> bool:
    return init.state == State.Done
