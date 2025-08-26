from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

try:
    import pulp  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - handled at call site
    pulp = None  # type: ignore[assignment]

from tmiplus.adapters.base import DataAdapter
from tmiplus.config.loader import ensure_config
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


def plan_ilp_pref(
    adapter: DataAdapter,
    dfrom: date,
    dto: date,
    recreate: bool,
    *,
    msg: bool = False,
) -> PlanResult:
    if pulp is None:
        raise RuntimeError(
            "ILP planner requires the optional 'ilp' extra. Install with: pip install '.[ilp]'"
        )

    cfg = ensure_config().planner.ilp_pref
    weights = cfg.weights

    members = [m for m in adapter.list_members() if m.active]
    initiatives = [i for i in adapter.list_initiatives() if not is_done(i)]
    assignments_existing = adapter.list_assignments()

    weeks = [date_to_str(wk) for wk in iter_weeks(dfrom, dto)]

    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    busy = (
        {(a.member_name, a.week_start) for a in assignments_existing}
        if not recreate
        else set()
    )

    # Goals and eligibility
    target_pw: dict[str, float] = {}
    for i in initiatives:
        est = _effective_estimate_pw(i)
        if est is not None:
            target_pw[i.name] = est

    # Remove children with missing-dependency goals
    for ini_name in list(target_pw.keys()):
        ini_obj = next((x for x in initiatives if x.name == ini_name), None)
        if ini_obj and ini_obj.depends_on:
            for dep in ini_obj.depends_on:
                if dep not in target_pw:
                    target_pw.pop(ini_name, None)
                    break

    prob = pulp.LpProblem("tmi_plan_ilp_pref", pulp.LpMaximize)  # type: ignore[attr-defined]

    y: dict[tuple[str, str, str], Any] = {}
    x: dict[tuple[str, str, str], Any] = {}
    z: dict[str, Any] = {
        i.name: pulp.LpVariable(f"z_{i.name}", lowBound=0, upBound=1, cat=pulp.LpBinary)  # type: ignore[attr-defined]
        for i in initiatives
        if i.name in target_pw
    }
    y_active: dict[tuple[str, str], Any] = {}
    p_planned: dict[str, Any] = {
        name: pulp.LpVariable(f"pplan__{name}", lowBound=0, upBound=1, cat=pulp.LpBinary)  # type: ignore[attr-defined]
        for name in target_pw.keys()
    }

    allowed_by_init: dict[str, set[str]] = {}
    for i in initiatives:
        allowed_by_init[i.name] = set(allowed_pool_members(adapter, i))

    # Decision variables
    for i in initiatives:
        if i.name not in target_pw:
            continue
        for m in members:
            if m.name not in allowed_by_init[i.name]:
                continue
            for w in weeks:
                if i.start_after and i.start_after > w:
                    continue
                if (m.name, w) in pto or (m.name, w) in busy:
                    continue
                dec_key = (m.name, i.name, w)
                y[dec_key] = pulp.LpVariable(  # type: ignore[assignment]
                    f"y_{m.name}_{i.name}_{w}",
                    lowBound=0.0,
                    upBound=m.weekly_capacity_pw,
                    cat=pulp.LpContinuous,
                )
                x[dec_key] = pulp.LpVariable(  # type: ignore[assignment]
                    f"x_{m.name}_{i.name}_{w}", lowBound=0, upBound=1, cat=pulp.LpBinary
                )
                y_active[(i.name, w)] = pulp.LpVariable(  # type: ignore[assignment]
                    f"yact__{i.name}__{w}", lowBound=0, upBound=1, cat=pulp.LpBinary
                )

    # Global capacity coherence
    for m in members:
        for w in weeks:
            vars_mw = [v for (mm, _, ww), v in y.items() if mm == m.name and ww == w]
            xs_mw = [v for (mm, _, ww), v in x.items() if mm == m.name and ww == w]
            if vars_mw:
                prob += pulp.lpSum(vars_mw) <= m.weekly_capacity_pw  # type: ignore[attr-defined]
            if xs_mw:
                prob += pulp.lpSum(xs_mw) <= 1  # type: ignore[attr-defined]

    # Initiative target bounds and completion link
    for i in initiatives:
        if i.name not in target_pw:
            continue
        vars_i = [v for (_, ii, _), v in y.items() if ii == i.name]
        if vars_i:
            prob += pulp.lpSum(vars_i) <= target_pw[i.name]  # type: ignore[attr-defined]
            prob += pulp.lpSum(vars_i) >= target_pw[i.name] * z[i.name]  # type: ignore[attr-defined]

    # Link y to x and x to y_active; link y_active to p_planned
    cap_map = {m.name: m.weekly_capacity_pw for m in members}
    for (m_name, i_name, w), y_var in y.items():
        prob += y_var <= cap_map[m_name] * x[(m_name, i_name, w)]  # type: ignore[operator]
        prob += y_active[(i_name, w)] >= x[(m_name, i_name, w)]  # type: ignore[operator]
        prob += y_active[(i_name, w)] <= p_planned[i_name]  # type: ignore[operator]
    # Ensure p_planned cannot be 1 without activity
    for i_name in p_planned.keys():
        active_weeks = [y_active[(i_name, w)] for w in weeks if (i_name, w) in y_active]
        if active_weeks:
            prob += pulp.lpSum(active_weeks) >= p_planned[i_name]  # type: ignore[attr-defined]

    # Dependency precedence (hard)
    for child in initiatives:
        if not child.depends_on or child.name not in target_pw:
            continue
        for dep in child.depends_on:
            if dep not in target_pw:
                continue
            tail_sums = []
            running: list[Any] = []
            for w in reversed(weeks):
                running.append(y_active[(dep, w)])
                tail_sums.append(pulp.lpSum(running))  # type: ignore[attr-defined]
            tail_sums.reverse()
            for k, w in enumerate(weeks):
                prob += y_active[(child.name, w)] + tail_sums[k] <= 1  # type: ignore[operator]
            prob += p_planned[child.name] <= p_planned[dep]  # type: ignore[operator]
            # Child can only be active if dependency is fully staffed
            for w in weeks:
                prob += y_active[(child.name, w)] <= z[dep]  # type: ignore[operator]

    # Preferred squad encouragement (soft): bonus when staffed by preferred squad
    def squad_bonus_terms() -> list[Any]:
        terms: list[Any] = []
        for (m_name, i_name, _w), x_var in x.items():
            ini = next((ii for ii in initiatives if ii.name == i_name), None)
            mem = next((mm for mm in members if mm.name == m_name), None)
            if ini and mem and ini.pref_squad and mem.squad_label == ini.pref_squad:
                terms.append(x_var)
        return terms

    # Roadmap share: soft target around W.roadmap_target_ratio
    roadmap_terms = []
    for (_m_name, i_name, _w), y_var in y.items():
        ini = next((ii for ii in initiatives if ii.name == i_name), None)
        if ini and ini.budget.value == "Roadmap":
            roadmap_terms.append(y_var)

    total_assigned = pulp.lpSum(v for v in y.values())  # type: ignore[attr-defined]
    roadmap_assigned = pulp.lpSum(roadmap_terms) if roadmap_terms else 0  # type: ignore[assignment]

    # Deadline penalty: count active weeks after required_by
    deadline_penalties: list[Any] = []
    for i in initiatives:
        if i.name not in target_pw or not i.required_by:
            continue
        for w in weeks:
            if w > i.required_by:
                deadline_penalties.append(y_active[(i.name, w)])

    # Objective construction
    completion_weighted = pulp.lpSum(
        (
            (
                weights.completion_weight_base
                * (6 - ii.priority)
                * (weights.priority1_multiplier if ii.priority == 1 else 1.0)
            )
            * z[ii.name]
        )
        for ii in initiatives
        if ii.name in z
    )  # type: ignore[attr-defined]
    utilization_term = weights.utilization_weight * total_assigned  # type: ignore[operator]
    breadth_term = weights.breadth_weight * pulp.lpSum(p_planned.values())  # type: ignore[attr-defined]
    pref_term = weights.pref_squad_bonus * pulp.lpSum(squad_bonus_terms())  # type: ignore[attr-defined]
    deadline_term = -weights.deadline_penalty_per_week * pulp.lpSum(deadline_penalties)  # type: ignore[attr-defined]

    # Roadmap deviation penalty ~ quadratic-ish via two-sided linearization (approx):
    # Penalize |roadmap_assigned / total_assigned - target|
    # Approximate with difference from target * total_assigned
    roadmap_deviation = pulp.lpSum([])  # type: ignore[assignment]
    if roadmap_terms:
        roadmap_deviation = weights.roadmap_deviation_penalty * pulp.lpSum([roadmap_assigned - weights.roadmap_target_ratio * total_assigned])  # type: ignore[attr-defined]

    prob += (
        completion_weighted
        + utilization_term
        + breadth_term
        + pref_term
        + deadline_term
        - roadmap_deviation
    )  # type: ignore[operator]

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=cfg.time_limit_s)  # type: ignore[attr-defined]
    if cfg.mip_gap is not None:
        solver.options.append(f"ratioGap={cfg.mip_gap}")  # type: ignore[attr-defined]
    if cfg.threads and cfg.threads > 0:
        solver.threads = cfg.threads  # type: ignore[attr-defined]
    res = prob.solve(solver)

    # Extract plan
    plan_assignments: list[Assignment] = []
    eps = 1e-6
    for (m_name, i_name, w), var in y.items():
        val = float(var.value() or 0.0)  # type: ignore[misc]
        if val > eps:
            plan_assignments.append(
                Assignment(
                    member_name=m_name,
                    initiative_name=i_name,
                    week_start=w,
                    week_end=week_end_from_start_str(w),
                    capacity_pw=round(val, 3),
                )
            )

    # Unstaffed summary
    unstaffed: list[dict[str, object]] = []
    for i in initiatives:
        if i.name not in target_pw:
            continue
        z_val = z[i.name].value()  # type: ignore[misc]
        if z_val is None or z_val < 0.5:
            assigned_i = sum(
                float(y[(m.name, i.name, w)].value() or 0.0)  # type: ignore[misc]
                for m in members
                for w in weeks
                if (m.name, i.name, w) in y
            )
            unstaffed.append(
                {
                    "initiative": i.name,
                    "required_pw": target_pw[i.name],
                    "available_pw": round(assigned_i, 3),
                    "reason": "Not fully staffed in window",
                }
            )

    # Optional idle fill
    if cfg.enable_idle_fill:
        busy_after = {(a.member_name, a.week_start) for a in plan_assignments}
        latest_by_init: dict[str, str] = {}
        assigned_by_init: dict[str, float] = {}
        for a in plan_assignments:
            cur = latest_by_init.get(a.initiative_name)
            if cur is None or a.week_start > cur:
                latest_by_init[a.initiative_name] = a.week_start
            assigned_by_init[a.initiative_name] = assigned_by_init.get(
                a.initiative_name, 0.0
            ) + float(a.capacity_pw or 0.0)
        remaining_by_init: dict[str, float] = {
            name: max(0.0, target_pw.get(name, 0.0) - assigned_by_init.get(name, 0.0))
            for name in target_pw.keys()
        }
        for w in weeks:
            for m in members:
                if (m.name, w) in busy_after or (m.name, w) in pto:
                    continue
                # choose best candidate (priority, required_by, name) with remaining > 0
                best: tuple[int, str, str] | None = None
                best_name: str | None = None
                for i in initiatives:
                    if i.name not in target_pw:
                        continue
                    if remaining_by_init.get(i.name, 0.0) <= 1e-6:
                        continue
                    if m.name not in allowed_by_init.get(i.name, set()):
                        continue
                    if i.start_after and i.start_after > w:
                        continue
                    ok_dep = True
                    for dep in i.depends_on or []:
                        dep_last = latest_by_init.get(dep)
                        if not dep_last or dep_last >= w:
                            ok_dep = False
                            break
                    if not ok_dep:
                        continue
                    req = i.required_by or "9999-12-31"
                    rank_key: tuple[int, str, str] = (i.priority, req, i.name)
                    if best is None or rank_key < best:
                        best = rank_key
                        best_name = i.name
                if best_name:
                    assign_pw = min(
                        remaining_by_init.get(best_name, 0.0),
                        float(m.weekly_capacity_pw),
                    )
                    if assign_pw <= 1e-6:
                        continue
                    plan_assignments.append(
                        Assignment(
                            member_name=m.name,
                            initiative_name=best_name,
                            week_start=w,
                            week_end=week_end_from_start_str(w),
                            capacity_pw=round(assign_pw, 3),
                        )
                    )
                    busy_after.add((m.name, w))
                    remaining_by_init[best_name] = max(
                        0.0, remaining_by_init.get(best_name, 0.0) - assign_pw
                    )
                    cur = latest_by_init.get(best_name)
                    if cur is None or w > cur:
                        latest_by_init[best_name] = w

    total_pw = round(sum(a.capacity_pw or 0.0 for a in plan_assignments), 3)
    summary: dict[str, object] = {
        "ilp_status": pulp.LpStatus[res],  # type: ignore[index]
        "ilp_objective": float(pulp.value(prob.objective) or 0.0),  # type: ignore[arg-type]
        "initiatives_considered": len([i for i in initiatives if i.name in target_pw]),
        "initiatives_planned": len({a.initiative_name for a in plan_assignments}),
        "initiatives_unstaffed": len(unstaffed),
        "total_person_weeks": total_pw,
    }
    return PlanResult(
        assignments=plan_assignments, unstaffed=unstaffed, summary=summary
    )
