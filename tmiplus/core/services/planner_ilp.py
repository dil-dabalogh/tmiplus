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


def plan_ilp(
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

    members = [m for m in adapter.list_members() if m.active]
    initiatives = [i for i in adapter.list_initiatives() if not is_done(i)]
    assignments_existing = adapter.list_assignments()

    # Build time grid
    weeks = [date_to_str(wk) for wk in iter_weeks(dfrom, dto)]

    # Availability maps
    pto = {(p.member_name, p.week_start) for p in adapter.list_pto()}
    busy = (
        {(a.member_name, a.week_start) for a in assignments_existing}
        if not recreate
        else set()
    )

    # Goals
    target_pw: dict[str, float] = {}
    for i in initiatives:
        est = _effective_estimate_pw(i)
        if est is not None:
            target_pw[i.name] = est
    # Enforce dependency presence: if an initiative depends on another that has no
    # target (no estimate), drop the child from goals so it can't be planned alone
    for i in initiatives:
        if i.name in target_pw and i.depends_on:
            for dep in i.depends_on:
                if dep not in target_pw:
                    target_pw.pop(i.name, None)
                    break
    if not target_pw:
        return PlanResult(
            assignments=[],
            unstaffed=[],
            summary={
                "ilp_status": "no-goals",
                "ilp_solve_seconds": 0.0,
                "ilp_num_variables": 0,
                "ilp_num_constraints": 0,
            },
        )

    cfg = ensure_config().planner.ilp
    weights = cfg.weights

    # Model
    prob = pulp.LpProblem("tmi_plan_ilp", pulp.LpMaximize)  # type: ignore[attr-defined]

    # Decision variables: y[m,i,w] person-weeks allocated (continuous >=0)
    y: dict[tuple[str, str, str], Any] = {}
    # Binary assignment decisions x[m,i,w]
    x: dict[tuple[str, str, str], Any] = {}
    # Binary z[i] -> 1 if initiative i fully staffed
    z: dict[str, Any] = {
        i.name: pulp.LpVariable(f"z_{i.name}", lowBound=0, upBound=1, cat=pulp.LpBinary)  # type: ignore[attr-defined]
        for i in initiatives
        if i.name in target_pw
    }

    # Precompute allowed members per initiative
    allowed_by_init: dict[str, set[str]] = {}
    for i in initiatives:
        allowed_by_init[i.name] = set(allowed_pool_members(adapter, i))

    # Create variables only when allowed, available, and within StartAfter window (explicit only)
    for i in initiatives:
        if i.name not in target_pw:
            continue
        for m in members:
            if m.name not in allowed_by_init[i.name]:
                continue
            for w in weeks:
                # Respect explicit StartAfter (dependencies enforced by constraints below)
                if i.start_after and i.start_after > w:
                    continue
                if (m.name, w) in pto:
                    continue
                if (m.name, w) in busy:
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

    # Constraints
    # Squad all-or-none: For each (initiative, week), either the entire squad is assigned or none.
    # Build squads by label
    squads_by_label: dict[str, list[str]] = {}
    for m in members:
        if m.squad_label:
            squads_by_label.setdefault(m.squad_label, []).append(m.name)

    # For each initiative and week, enforce all-or-none per squad
    for i in initiatives:
        if i.name not in target_pw:
            continue
        for w in weeks:
            for _label, squad_members in squads_by_label.items():
                # Determine which members have decision vars for this (i,w)
                vars_present = [mm for mm in squad_members if (mm, i.name, w) in x]
                if not vars_present:
                    continue
                if len(vars_present) == len(squad_members):
                    # All members eligible -> tie their x equal (all-or-none)
                    anchor = vars_present[0]
                    for mm in vars_present[1:]:
                        prob += x[(mm, i.name, w)] <= x[(anchor, i.name, w)]  # type: ignore[operator]
                        prob += x[(anchor, i.name, w)] <= x[(mm, i.name, w)]  # type: ignore[operator]
                else:
                    # Some squad members are ineligible this week -> forbid squad assignment
                    for mm in vars_present:
                        prob += x[(mm, i.name, w)] <= 0  # type: ignore[operator]

    # Link capacity to assignment decisions and enforce member weekly capacity and one-initiative-per-week
    # Link capacity to assignment decisions and enforce member weekly capacity and one-initiative-per-week
    for m in members:
        for w in weeks:
            vars_mw = [v for (mm, _, ww), v in y.items() if mm == m.name and ww == w]
            xs_mw = [v for (mm, _, ww), v in x.items() if mm == m.name and ww == w]
            if vars_mw:
                # capacity link and weekly limit
                prob += pulp.lpSum(vars_mw) <= m.weekly_capacity_pw  # type: ignore[attr-defined]
            if xs_mw:
                prob += pulp.lpSum(xs_mw) <= 1  # type: ignore[attr-defined]

    # Initiative completion and upper bound to target
    for i in initiatives:
        if i.name not in target_pw:
            continue
        vars_i = [v for (_, ii, _), v in y.items() if ii == i.name]
        if vars_i:
            prob += pulp.lpSum(vars_i) <= target_pw[i.name]  # type: ignore[attr-defined]
            prob += pulp.lpSum(vars_i) >= target_pw[i.name] * z[i.name]  # type: ignore[attr-defined]

    # Link y to x: y[m,i,w] <= cap(m) * x[m,i,w]
    cap_map = {m.name: m.weekly_capacity_pw for m in members}
    for (m_name, i_name, w), y_var in y.items():
        prob += y_var <= cap_map[m_name] * x[(m_name, i_name, w)]  # type: ignore[operator]

    # Member contiguity penalties: transitions per (m,i) across weeks
    # Introduce t+ and t- (continuous [0,1]) to measure |x[w] - x[w_prev]|
    week_index: dict[str, int] = {w: idx for idx, w in enumerate(weeks)}

    def _prev_week(w: str) -> str | None:
        idx = week_index[w]
        return weeks[idx - 1] if idx > 0 else None

    t_pos: dict[tuple[str, str, str], Any] = {}
    t_neg: dict[tuple[str, str, str], Any] = {}
    for m_name, i_name, w in x.keys():
        t_pos[(m_name, i_name, w)] = pulp.LpVariable(f"tpos__{m_name}__{i_name}__{w}", lowBound=0, upBound=1)  # type: ignore[assignment]
        t_neg[(m_name, i_name, w)] = pulp.LpVariable(f"tneg__{m_name}__{i_name}__{w}", lowBound=0, upBound=1)  # type: ignore[assignment]
        pw = _prev_week(w)
        if pw is not None and (m_name, i_name, pw) in x:
            prob += t_pos[(m_name, i_name, w)] >= x[(m_name, i_name, w)] - x[(m_name, i_name, pw)]  # type: ignore[operator]
            prob += t_neg[(m_name, i_name, w)] >= x[(m_name, i_name, pw)] - x[(m_name, i_name, w)]  # type: ignore[operator]
        else:
            prob += t_pos[(m_name, i_name, w)] >= x[(m_name, i_name, w)]  # type: ignore[operator]
            prob += t_neg[(m_name, i_name, w)] >= 0  # type: ignore[operator]

    # Initiative active-week indicators and transitions to compress span
    y_active: dict[tuple[str, str], Any] = {}
    y_t_pos: dict[tuple[str, str], Any] = {}
    y_t_neg: dict[tuple[str, str], Any] = {}
    # Planned indicator per initiative: 1 if active in any week
    p_planned: dict[str, Any] = {
        i_name: pulp.LpVariable(f"pplan__{i_name}", lowBound=0, upBound=1, cat=pulp.LpBinary)  # type: ignore[attr-defined]
        for i_name in target_pw.keys()
    }
    for i_name in target_pw.keys():
        for w in weeks:
            y_active[(i_name, w)] = pulp.LpVariable(f"yact__{i_name}__{w}", lowBound=0, upBound=1, cat=pulp.LpBinary)  # type: ignore[assignment]
            y_t_pos[(i_name, w)] = pulp.LpVariable(f"yatpos__{i_name}__{w}", lowBound=0, upBound=1)  # type: ignore[assignment]
            y_t_neg[(i_name, w)] = pulp.LpVariable(f"yatneg__{i_name}__{w}", lowBound=0, upBound=1)  # type: ignore[assignment]
            # link activity: if any x is 1, y_active must be 1
            xs_iw = [
                x[(m_name, i_name, w)]
                for (m_name, ii, ww) in x.keys()
                if ii == i_name and ww == w
            ]
            if xs_iw:
                for var in xs_iw:
                    prob += y_active[(i_name, w)] >= var  # type: ignore[operator]
            # transitions
            pw = _prev_week(w)
            if pw is not None:
                prob += y_t_pos[(i_name, w)] >= y_active[(i_name, w)] - y_active[(i_name, pw)]  # type: ignore[operator]
                prob += y_t_neg[(i_name, w)] >= y_active[(i_name, pw)] - y_active[(i_name, w)]  # type: ignore[operator]
            else:
                prob += y_t_pos[(i_name, w)] >= y_active[(i_name, w)]  # type: ignore[operator]
                prob += y_t_neg[(i_name, w)] >= 0  # type: ignore[operator]
            # Link active to planned indicator
            prob += y_active[(i_name, w)] <= p_planned[i_name]  # type: ignore[operator]

    # Dependency precedence: for each dependency (dep -> child), child cannot be active
    # in a week <= any week the dependency is still active. Enforce with cumulative constraint.
    for child in initiatives:
        if not child.depends_on or child.name not in target_pw:
            continue
        for dep_name in child.depends_on:
            if dep_name not in target_pw:
                continue
            # If child is planned at all, dependency must be planned at least partially
            prob += p_planned[child.name] <= p_planned[dep_name]  # type: ignore[operator]
            # For each week index k, child[k] + sum_{t>=k} dep[t] <= 1
            tail_sums: list[Any] = []
            running = []
            for w in reversed(weeks):
                running.append(y_active[(dep_name, w)])
                tail_sums.append(pulp.lpSum(running))  # type: ignore[attr-defined]
            tail_sums = list(reversed(tail_sums))
            for k, w in enumerate(weeks):
                prob += y_active[(child.name, w)] + tail_sums[k] <= 1  # type: ignore[operator]

    # Dependency completion: a child can be marked fully staffed only if all its dependencies are
    # also fully staffed. Enforce z_child <= z_dep for each dependency.
    for child in initiatives:
        if not child.depends_on or child.name not in target_pw:
            continue
        for dep_name in child.depends_on:
            if dep_name in z and child.name in z:
                prob += z[child.name] <= z[dep_name]  # type: ignore[operator]

    # Objective: prioritize full completions (weighted by priority), planned breadth, then total assigned
    big = float(weights.complete_priority_weight)
    full_weight = pulp.lpSum(  # type: ignore[attr-defined]
        (big * (6 - i.priority)) * z[i.name] for i in initiatives if i.name in z
    )
    # Encourage planning more initiatives (breadth) with small weight
    breadth_bonus = 0.1 * pulp.lpSum(p_planned[i_name] for i_name in p_planned.keys())  # type: ignore[attr-defined]
    total_assigned = pulp.lpSum(v for v in y.values())  # type: ignore[attr-defined]
    # Penalties/bonuses
    member_switch_penalty = pulp.lpSum((t_pos[k] + t_neg[k]) * weights.member_chunk_transition_penalty for k in t_pos.keys())  # type: ignore[attr-defined]
    init_span_penalty = pulp.lpSum((y_t_pos[k] + y_t_neg[k]) * weights.init_span_transition_penalty for k in y_t_pos.keys())  # type: ignore[attr-defined]
    init_active_penalty = pulp.lpSum(y_active[k] * weights.init_active_week_penalty for k in y_active.keys())  # type: ignore[attr-defined]
    # Early week bonus
    week_idx = {w: idx for idx, w in enumerate(weeks)}
    horizon = max(1, len(weeks))
    early_bonus = pulp.lpSum((horizon - week_idx[w]) * weights.early_week_bonus * x[(m_name, i_name, w)] for (m_name, i_name, w) in x.keys())  # type: ignore[attr-defined]

    prob += full_weight + breadth_bonus + total_assigned + early_bonus - member_switch_penalty - init_span_penalty - init_active_penalty  # type: ignore[operator]

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=cfg.time_limit_s)  # type: ignore[attr-defined]
    if cfg.mip_gap is not None:
        # CBC uses ratioGap
        solver.options.append(f"ratioGap={cfg.mip_gap}")  # type: ignore[attr-defined]
    if cfg.threads and cfg.threads > 0:
        solver.threads = cfg.threads  # type: ignore[attr-defined]
    res = prob.solve(solver)

    # Build assignments from y > 0
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

    # Unstaffed list: initiatives where z[i]==0
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
                    "reason": "Not enough capacity in window (partial allowed; not fully staffed)",
                }
            )

    # --------------------- Idle capacity fill pass (greedy) ---------------------
    # Goal: utilize free member-weeks for initiatives that were not fully staffed
    # while respecting pools, PTO, one-initiative-per-week, StartAfter, and dependency precedence
    # based on the ILP-produced schedule (finish-to-start using latest dependency week).

    # Compute existing busy weeks from ILP assignments
    busy_after_ilp = {(a.member_name, a.week_start) for a in plan_assignments}
    # Allowed members per initiative (cache)
    allowed_by_init_fill: dict[str, set[str]] = {}
    for i in initiatives:
        allowed_by_init_fill[i.name] = set(allowed_pool_members(adapter, i))

    # Build dependency latest-week map from ILP assignments
    latest_week_by_init: dict[str, str] = {}
    for a in plan_assignments:
        lw = latest_week_by_init.get(a.initiative_name)
        if lw is None or a.week_start > lw:
            latest_week_by_init[a.initiative_name] = a.week_start

    inits_by_name: dict[str, Initiative] = {i.name: i for i in initiatives}
    # Candidate initiatives for idle fill: those that are currently unstaffed (not fully staffed)
    unstaffed_names: set[str] = {str(d.get("initiative", "")) for d in unstaffed}

    # Build PTO map for quick checks (already above as 'pto')

    # Iterate weeks and members to allocate idle
    for wk in weeks:
        for m in members:
            # Must be free this week
            if (m.name, wk) in busy_after_ilp:
                continue
            if (m.name, wk) in pto:
                continue
            # Choose the best candidate initiative
            best_name: str | None = None
            best_key: tuple[int, str, str] | None = None
            for ini_name in sorted(unstaffed_names):
                ini = inits_by_name.get(ini_name)
                if not ini:
                    continue
                # Pool/eligibility
                if m.name not in allowed_by_init_fill.get(ini_name, set()):
                    continue
                # StartAfter gating
                if ini.start_after and ini.start_after > wk:
                    continue
                # Dependency precedence: each dependency must have a latest week < current week
                ok_dep = True
                for dep in ini.depends_on or []:
                    dep_last = latest_week_by_init.get(dep)
                    if not dep_last or dep_last >= wk:
                        ok_dep = False
                        break
                if not ok_dep:
                    continue
                # Rank by priority asc, required_by asc (empty last), name as tie-breaker
                req = ini.required_by or "9999-12-31"
                rank_key: tuple[int, str, str] = (ini.priority, req, ini.name)
                if best_key is None or rank_key < best_key:
                    best_key = rank_key
                    best_name = ini_name
            if best_name:
                plan_assignments.append(
                    Assignment(
                        member_name=m.name,
                        initiative_name=best_name,
                        week_start=wk,
                        week_end=week_end_from_start_str(wk),
                        capacity_pw=m.weekly_capacity_pw,
                    )
                )
                busy_after_ilp.add((m.name, wk))
                # Update latest week for that initiative
                cur_last = latest_week_by_init.get(best_name)
                if cur_last is None or wk > cur_last:
                    latest_week_by_init[best_name] = wk

    summary: dict[str, object] = {
        "initiatives_considered": len([i for i in initiatives if i.name in target_pw]),
        "initiatives_planned": len({a.initiative_name for a in plan_assignments}),
        "initiatives_unstaffed": len(unstaffed),
        "total_person_weeks": round(
            sum(a.capacity_pw or 0.0 for a in plan_assignments), 3
        ),
        "ilp_status": pulp.LpStatus[res],  # type: ignore[index]
        "ilp_objective": float(pulp.value(prob.objective) or 0.0),  # type: ignore[arg-type]
        "ilp_num_variables": len(prob.variables()),  # type: ignore[arg-type]
        "ilp_num_constraints": len(prob.constraints),  # type: ignore[arg-type]
        "weights": {
            "complete_priority_weight": weights.complete_priority_weight,
            "early_week_bonus": weights.early_week_bonus,
            "member_chunk_transition_penalty": weights.member_chunk_transition_penalty,
            "init_span_transition_penalty": weights.init_span_transition_penalty,
            "init_active_week_penalty": weights.init_active_week_penalty,
        },
    }

    return PlanResult(
        assignments=plan_assignments, unstaffed=unstaffed, summary=summary
    )
