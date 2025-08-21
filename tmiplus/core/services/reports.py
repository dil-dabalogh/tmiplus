from __future__ import annotations

from collections import defaultdict
from datetime import date

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.util.dates import date_to_str, iter_weeks


def budget_distribution(adapter: DataAdapter, dfrom: date, dto: date) -> dict[str, float]:
    # Person-weeks per budget category over the window; include Unassigned/Idle
    members = adapter.list_members()
    inits = {i.name: i for i in adapter.list_initiatives()}
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    assigns = adapter.list_assignments()

    # Build assignment map by (member, week_start) -> initiative_name
    assignment_by_week: dict[tuple[str, str], str] = {
        (a.member_name, a.week_start): a.initiative_name for a in assigns
    }

    totals = defaultdict(float)
    for wk in iter_weeks(dfrom, dto):
        wk_s = date_to_str(wk)
        # total capacity this week
        total_capacity = 0.0
        assigned_capacity = defaultdict(float)
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
