from __future__ import annotations

from dataclasses import dataclass
from datetime import date

try:
    import pulp  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - handled at call site
    pulp = None  # type: ignore[assignment]

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Assignment, Initiative
from tmiplus.core.services.validation import allowed_pool_members, is_done
from tmiplus.core.util.dates import date_to_str, iter_weeks, week_end_from_start_str


@dataclass
class PlanResult:
    assignments: list[Assignment]
    unstaffed: list[dict[str, object]]
    summary: dict[str, object]


def _effective_estimate_pw(init: Initiative) -> float | None:
    if init.granular_pw is not None:
        return float(init.granular_pw)
    if init.rom_pw is not None:
        return float(init.rom_pw)
    return None


def _weeks(dfrom: date, dto: date) -> list[str]:
    return [date_to_str(w) for w in iter_weeks(dfrom, dto)]


def plan_ilp(
    adapter: DataAdapter, dfrom: date, dto: date, recreate: bool
) -> PlanResult:
    if pulp is None:
        raise RuntimeError(
            "ILP planner requires the optional 'ilp' extra. Install with: pip install '.[ilp]'"
        )

    members = [m for m in adapter.list_members() if m.active]
    initiatives = [i for i in adapter.list_initiatives() if not is_done(i)]
    assignments_existing = adapter.list_assignments()
    # No need for member index beyond capacity lookup (cap_m)

    # Targets per initiative (person-weeks) using effective estimate (Granular > ROM)
    target_pw: dict[str, float] = {}
    for i in initiatives:
        est = _effective_estimate_pw(i)
        if est is not None:
            target_pw[i.name] = est

    # Consider only initiatives that have an effective estimate
    considered_inits: list[Initiative] = [i for i in initiatives if i.name in target_pw]

    wks = _weeks(dfrom, dto)
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    busy = (
        {(a.member_name, a.week_start) for a in assignments_existing}
        if not recreate
        else set()
    )

    # Variables: x[m,w,i] in {0,1} assign member m in week w to initiative i
    model = pulp.LpProblem("TMI_ILP_Planner", pulp.LpMaximize)  # type: ignore[attr-defined]

    # Pre-compute allowed tuples and their weekly capacities
    allowed_tuples: list[tuple[str, str, str]] = []  # (m, w, i)
    cap_m: dict[str, float] = {m.name: m.weekly_capacity_pw for m in members}
    for i in considered_inits:
        allowed_members = allowed_pool_members(adapter, i)
        for w in wks:
            # Respect StartAfter
            if i.start_after and i.start_after > w:
                continue
            for m in members:
                if m.name not in allowed_members:
                    continue
                if (m.name, w) in pto or (m.name, w) in busy:
                    continue
                allowed_tuples.append((m.name, w, i.name))

    x = pulp.LpVariable.dicts(
        "x",
        ((m, w, i) for (m, w, i) in allowed_tuples),
        lowBound=0,
        upBound=1,
        cat=pulp.LpBinary,  # type: ignore[attr-defined]
    )

    # Objective: prioritize higher priority initiatives, earlier deadlines; simple scoring
    def score(init: Initiative) -> float:
        base = 100.0 - 10.0 * (init.priority - 1)
        # Small boost if deadline exists
        if init.required_by:
            base += 5.0
        return base

    init_by_name = {i.name: i for i in considered_inits}
    model += pulp.lpSum(  # type: ignore[attr-defined]
        score(init_by_name[i]) * cap_m[m] * x[(m, w, i)] for (m, w, i) in allowed_tuples
    )

    # Constraints
    # 1) Member can do at most one initiative per week
    for m in members:
        for w in wks:
            vars_mw = [
                x[(mm, ww, i)]
                for (mm, ww, i) in allowed_tuples
                if mm == m.name and ww == w
            ]
            if vars_mw:
                model += pulp.lpSum(vars_mw) <= 1  # type: ignore[attr-defined]

    # 2) Each initiative total assigned capacity cannot exceed its target
    for i_name, target in target_pw.items():
        vars_i = [
            cap_m[m] * x[(m, w, ii)] for (m, w, ii) in allowed_tuples if ii == i_name
        ]
        if vars_i:
            model += pulp.lpSum(vars_i) <= target  # type: ignore[attr-defined]

    # Solve
    model.solve(pulp.PULP_CBC_CMD(msg=False))  # type: ignore[attr-defined]

    # Collect solution
    plan_assignments: list[Assignment] = []
    for m_name, w_s, i_name in allowed_tuples:
        var = x[(m_name, w_s, i_name)]
        if var.value() and var.value() > 0.5:  # type: ignore[call-arg]
            plan_assignments.append(
                Assignment(
                    member_name=m_name,
                    initiative_name=i_name,
                    week_start=w_s,
                    week_end=week_end_from_start_str(w_s),
                )
            )

    # Compute unstaffed
    assigned_pw: dict[str, float] = dict.fromkeys(target_pw, 0.0)
    for a in plan_assignments:
        assigned_pw[a.initiative_name] = assigned_pw.get(
            a.initiative_name, 0.0
        ) + cap_m.get(a.member_name, 0.0)

    unstaffed: list[dict[str, object]] = []
    for i_name, target in target_pw.items():
        avail = assigned_pw.get(i_name, 0.0)
        if avail + 1e-6 < target:
            unstaffed.append(
                {
                    "initiative": i_name,
                    "required_pw": float(target),
                    "available_pw": float(avail),
                    "reason": "Not enough capacity in window (no partial completion).",
                }
            )

    summary: dict[str, object] = {
        "initiatives_considered": len(considered_inits),
        "initiatives_planned": len({a.initiative_name for a in plan_assignments}),
        "initiatives_unstaffed": len(unstaffed),
        "total_person_weeks": float(sum(m.weekly_capacity_pw for m in members)),
    }

    return PlanResult(
        assignments=plan_assignments, unstaffed=unstaffed, summary=summary
    )
