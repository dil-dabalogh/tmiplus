from __future__ import annotations

from collections import defaultdict
from datetime import date

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
        for m in members:
            cap = m.weekly_capacity_pw
            total_capacity += cap
            if (m.name, wk_s) in pto:
                # PTO blocks entire week (treated as not available)
                continue
            if (m.name, wk_s) in assignment_by_week:
                init_name = assignment_by_week[(m.name, wk_s)]
                if init_name in inits:
                    cat = inits[init_name].budget.value
                    assigned_capacity[cat] += cap

        for cat, cap in assigned_capacity.items():
            totals[cat] += cap

        used = sum(assigned_capacity.values())
        idle = max(0.0, total_capacity - used)  # PTO reduces availability implicitly
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
