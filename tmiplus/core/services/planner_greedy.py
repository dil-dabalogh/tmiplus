from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set
from datetime import date
from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Assignment, Initiative, Member, State
from tmiplus.core.util.dates import iter_weeks, date_to_str, week_end_from_start_str
from tmiplus.core.services.validation import allowed_pool_members, is_done

@dataclass
class PlanResult:
    assignments: List[Assignment]
    unstaffed: List[Dict[str, object]]
    summary: Dict[str, object]

def _effective_estimate_pw(init: Initiative) -> float | None:
    if init.granular_pw is not None:
        return float(init.granular_pw)
    if init.rom_pw is not None:
        return float(init.rom_pw)
    return None

def _rank_key(init: Initiative) -> Tuple[int, str, str]:
    return (init.priority, init.required_by or "9999-12-31", init.start_after or "0001-01-01")

def _squad_groups(members: List[Member]) -> Dict[str, List[Member]]:
    groups: Dict[str, List[Member]] = {}
    for m in members:
        label = m.squad_label or f"__solo__/{m.name}"
        groups.setdefault(label, []).append(m)
    return groups

def _remaining_needed(init: Initiative, taken_pw: float, target: float) -> float:
    rem = max(0.0, target - taken_pw)
    return rem

def plan_greedy(adapter: DataAdapter, dfrom: date, dto: date, recreate: bool) -> PlanResult:
    members = [m for m in adapter.list_members() if m.active]
    initiatives = [i for i in adapter.list_initiatives() if not is_done(i)]
    assignments_existing = adapter.list_assignments()

    goal_map: Dict[str, float] = {}
    for i in initiatives:
        est = _effective_estimate_pw(i)
        if est is None:
            continue
        goal_map[i.name] = est

    # When NOT recreate, count existing assignments toward goals (only not-Done initiatives)
    taken_by_init_week: Dict[Tuple[str, str], float] = {}
    if not recreate:
        for a in assignments_existing:
            if a.initiative_name in goal_map:
                taken_by_init_week[(a.initiative_name, a.week_start)] = taken_by_init_week.get((a.initiative_name, a.week_start), 0.0) + 0.0  # placeholder not used
        # We'll sum taken per initiative below
    taken_by_init_total: Dict[str, float] = {k: 0.0 for k in goal_map}
    if not recreate:
        for a in assignments_existing:
            if a.initiative_name in goal_map:
                # get capacity of member
                m = next((mm for mm in members if mm.name == a.member_name), None)
                if m:
                    taken_by_init_total[a.initiative_name] += m.weekly_capacity_pw

    # PTO map
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}

    # availability map (member, week) -> bool free
    busy = {(a.member_name, a.week_start) for a in assignments_existing} if not recreate else set()

    # Plan result
    plan_assignments: List[Assignment] = []
    unstaffed: List[Dict[str, object]] = []

    # Rank initiatives
    plan_inits = sorted([i for i in initiatives if _effective_estimate_pw(i) is not None], key=_rank_key)

    # Iterate through weeks
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        # Build squad groups active this week
        groups = _squad_groups(members)

        for init in plan_inits:
            # Respect StartAfter
            if init.start_after and init.start_after > wk_s:
                continue

            target = goal_map[init.name]
            taken = taken_by_init_total.get(init.name, 0.0)
            rem = _remaining_needed(init, taken, target)
            if rem <= 0:
                continue

            # Allowed members by pool
            allowed = allowed_pool_members(adapter, init)

            # Build available squads: all members in the squad must be available
            for squad_label, squad_members in groups.items():
                names = [m.name for m in squad_members]
                if not set(names).issubset(allowed):
                    continue

                # all-or-none: squad is available only if EVERY member is free (not PTO, not busy)
                can_use = True
                total_cap = 0.0
                for m in squad_members:
                    if (m.name, wk_s) in pto:
                        can_use = False
                        break
                    if (m.name, wk_s) in busy:
                        can_use = False
                        break
                    total_cap += m.weekly_capacity_pw
                if not can_use:
                    continue

                # If squad fits (or overfills allowed per rule), assign entire squad
                # Overfill allowed: we still assign even if total_cap > rem
                # Apply assignments
                for m in squad_members:
                    plan_assignments.append(Assignment(
                        member_name=m.name,
                        initiative_name=init.name,
                        week_start=wk_s,
                        week_end=week_end_from_start_str(wk_s),
                    ))
                    busy.add((m.name, wk_s))
                    taken_by_init_total[init.name] = taken_by_init_total.get(init.name, 0.0) + m.weekly_capacity_pw

                # proceed to next initiative (one squad per initiative per week in greedy pass)
                break

    # After planning, determine which initiatives remain unstaffed (no partial completion allowed)
    for init in plan_inits:
        target = goal_map[init.name]
        taken = taken_by_init_total.get(init.name, 0.0)
        if taken < target:
            # Not fully staffed in window => remove any assignments we made for it and mark unstaffed
            plan_assignments = [a for a in plan_assignments if a.initiative_name != init.name]
            unstaffed.append({
                "initiative": init.name,
                "required_pw": target,
                "available_pw": taken,
                "reason": "Not enough capacity in window (no partial completion).",
            })

    summary = {
        "initiatives_considered": len(plan_inits),
        "initiatives_planned": len({a.initiative_name for a in plan_assignments}),
        "initiatives_unstaffed": len(unstaffed),
        "total_person_weeks": sum(
            next((m.weekly_capacity_pw for m in members if m.name == a.member_name), 0.0)
            for a in plan_assignments
        ),
    }
    return PlanResult(assignments=plan_assignments, unstaffed=unstaffed, summary=summary)
