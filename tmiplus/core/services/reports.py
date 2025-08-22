from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import cast

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.util.dates import date_to_str, iter_weeks


def budget_distribution(
    adapter: DataAdapter, dfrom: date, dto: date
) -> dict[str, float]:
    # Person-weeks per budget category over the window; include Unassigned/Idle
    members = adapter.list_members()
    inits = {i.name: i for i in adapter.list_initiatives()}
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    assigns = adapter.list_assignments()

    # Build assignment map by (member, week_start) -> initiative_name
    assignment_by_week: dict[tuple[str, str], str] = {
        (a.member_name, a.week_start): a.initiative_name for a in assigns
    }

    totals: dict[str, float] = defaultdict(float)
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        # total capacity this week
        total_capacity = 0.0
        assigned_capacity: dict[str, float] = defaultdict(float)
        pto_capacity = 0.0
        for m in members:
            cap = m.weekly_capacity_pw
            total_capacity += cap
            if (m.name, wk_s) in pto:
                # PTO: attribute capacity to PTO for this week
                pto_capacity += cap
                continue
            if (m.name, wk_s) in assignment_by_week:
                init_name = assignment_by_week[(m.name, wk_s)]
                if init_name in inits:
                    cat = inits[init_name].budget.value
                    assigned_capacity[cat] += cap

        for cat, cap in assigned_capacity.items():
            totals[cat] += cap

        used = sum(assigned_capacity.values())
        # Attribute PTO explicitly and compute idle as what's left
        totals["PTO"] += pto_capacity
        idle = max(0.0, total_capacity - used - pto_capacity)
        totals["Unassigned/Idle"] += idle

    return dict(sorted(totals.items(), key=lambda kv: kv[0]))


def _effective_estimate_pw(
    rom_pw: float | None, granular_pw: float | None
) -> tuple[float | None, str]:
    if granular_pw is not None:
        return float(granular_pw), "Granular"
    if rom_pw is not None:
        return float(rom_pw), "ROM"
    return None, "-"


def initiative_details(
    adapter: DataAdapter, dfrom: date, dto: date
) -> list[dict[str, object]]:
    """Compute initiative-level assigned person-weeks within the window.

    Returns a list of dicts with keys: name, budget, estimate_pw, estimate_type, assigned_pw.
    Only initiatives with non-zero assigned_pw are included.
    """
    members = adapter.list_members()
    inits = {i.name: i for i in adapter.list_initiatives()}
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    assigns = adapter.list_assignments()

    # Build assignment map by (member, week_start) -> initiative_name
    assignment_by_week: dict[tuple[str, str], str] = {
        (a.member_name, a.week_start): a.initiative_name for a in assigns
    }

    assigned_by_init: dict[str, float] = {}
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        for m in members:
            cap = m.weekly_capacity_pw
            if (m.name, wk_s) in pto:
                continue
            init_name = assignment_by_week.get((m.name, wk_s))
            if not init_name:
                continue
            if init_name in inits:
                assigned_by_init[init_name] = assigned_by_init.get(init_name, 0.0) + cap

    rows: list[dict[str, object]] = []
    for name, assigned in sorted(
        assigned_by_init.items(), key=lambda kv: kv[1], reverse=True
    ):
        init = inits.get(name)
        if not init:
            continue
        est, est_type = _effective_estimate_pw(init.rom_pw, init.granular_pw)
        rows.append(
            {
                "name": name,
                "budget": init.budget.value,
                "estimate_pw": est,
                "estimate_type": est_type,
                "assigned_pw": float(assigned),
            }
        )
    return rows


def pto_breakdown(adapter: DataAdapter, dfrom: date, dto: date) -> dict[str, float]:
    """Return total PTO allocation (person-weeks) by PTO type within the window.

    - Each PTO record is considered for its week_start only (weekly granularity)
    - A member on PTO consumes their full weekly capacity for that week
    """
    members = adapter.list_members()
    member_capacity = {m.name: m.weekly_capacity_pw for m in members}
    pto_rows = adapter.list_pto()

    # Map (member, week_start) -> type string
    pto_type_by_week: dict[tuple[str, str], str] = {}
    for p in pto_rows:
        pto_type_by_week[(p.member_name, p.week_start)] = p.type.value

    totals: dict[str, float] = defaultdict(float)
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        for m in members:
            t = pto_type_by_week.get((m.name, wk_s))
            if not t:
                continue
            totals[t] += member_capacity.get(m.name, 0.0)

    return dict(sorted(totals.items(), key=lambda kv: kv[0]))


def idle_capacity(
    adapter: DataAdapter, dfrom: date, dto: date
) -> list[dict[str, object]]:
    """Return total unallocated capacity (person-weeks) per member within the window.

    - PTO weeks are excluded (not counted as idle)
    - Any existing assignment in a week consumes that member's whole weekly capacity
    - Result is sorted by idle PW descending
    """
    members = adapter.list_members()
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    assigns = adapter.list_assignments()

    assignment_by_week: dict[tuple[str, str], str] = {
        (a.member_name, a.week_start): a.initiative_name for a in assigns
    }

    idle_by_member: dict[str, float] = {m.name: 0.0 for m in members}
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        for m in members:
            if (m.name, wk_s) in pto:
                continue
            if (m.name, wk_s) in assignment_by_week:
                continue
            idle_by_member[m.name] += m.weekly_capacity_pw

    rows: list[dict[str, object]] = [
        {"name": name, "idle_pw": float(pw)} for name, pw in idle_by_member.items()
    ]
    rows.sort(key=lambda d: cast(float, d["idle_pw"]), reverse=True)
    return rows
