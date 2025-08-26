from __future__ import annotations

from collections.abc import Sequence

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Assignment
from tmiplus.core.services.csv_io import read_assignments_csv, write_assignments_csv
from tmiplus.core.services.planner_greedy import PlanResult as GreedyPlanResult
from tmiplus.core.services.planner_greedy import plan_greedy
from tmiplus.core.services.planner_ilp import PlanResult as ILPPlanResult
from tmiplus.core.services.planner_ilp import plan_ilp
from tmiplus.core.services.planner_ilp_pref import (
    PlanResult as ILPPrefPlanResult,
)
from tmiplus.core.services.planner_ilp_pref import (
    plan_ilp_pref,
)
from tmiplus.core.util.dates import parse_date, week_end_from_start_str
from tmiplus.core.util.io import load_yaml, save_json, save_yaml
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

console = Console()

app = typer.Typer(help="Manage assignments")


@app.command(name="list")
def list_cmd() -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching assignments...", total=None)
        rows = a.list_assignments()
        progress.update(task, description="Rendering table...")
    print_table(
        "Assignments",
        ["Member", "Initiative", "WeekStart", "WeekEnd", "CapacityPW"],
        [
            [
                x.member_name,
                x.initiative_name,
                x.week_start,
                x.week_end or "",
                "" if x.capacity_pw is None else f"{x.capacity_pw}",
            ]
            for x in rows
        ],
    )


@app.command(name="import")
def import_(path: str = typer.Option(..., "--path")) -> None:
    a = get_adapter()
    items = read_assignments_csv(path)
    # Show progress bar while creating/updating assignments
    total = len(items)
    if total == 0:
        typer.echo("No assignments to import.")
        return
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Importing assignments...", total=total)
        # Process in batches to avoid excessive downstream recalculations
        batch_size = 25
        for i in range(0, total, batch_size):
            batch = items[i : i + batch_size]
            a.upsert_assignments(batch)
            progress.update(task, advance=len(batch))
    typer.echo(f"Imported {total} assignments.")


@app.command()
def export(out: str = typer.Option(..., "--out")) -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching assignments...", total=None)
        rows = a.list_assignments()
        progress.update(task, description="Writing CSV...")
        write_assignments_csv(out, rows)
    typer.echo(f"Wrote {out}.")


def _print_staffed_initiatives(
    a: DataAdapter,
    assignments: Sequence[Assignment],
    title: str = "Staffed Initiatives",
) -> None:
    members = a.list_members()
    member_capacity = {m.name: m.weekly_capacity_pw for m in members}
    inits = {i.name: i for i in a.list_initiatives()}

    def _eff_est(name: str) -> float | None:
        ini = inits.get(name)
        if not ini:
            return None
        if ini.granular_pw is not None:
            return float(ini.granular_pw)
        if ini.rom_pw is not None:
            return float(ini.rom_pw)
        return None

    assigned_by_init: dict[str, float] = {}
    eng_start_by_init: dict[str, str] = {}
    eng_end_by_init: dict[str, str] = {}
    for asg in assignments:
        cap = getattr(asg, "capacity_pw", None)
        member = getattr(asg, "member_name", getattr(asg, "member", ""))
        name = getattr(asg, "initiative_name", getattr(asg, "initiative", ""))
        if cap is None:
            cap = member_capacity.get(member, 0.0)
        assigned_by_init[name] = assigned_by_init.get(name, 0.0) + float(cap or 0.0)
        ws = getattr(asg, "week_start", "")
        we = getattr(asg, "week_end", None) or (
            week_end_from_start_str(ws) if ws else ""
        )
        cur_s = eng_start_by_init.get(name)
        cur_e = eng_end_by_init.get(name)
        if ws and (cur_s is None or ws < cur_s):
            eng_start_by_init[name] = ws
        if we and (cur_e is None or we > cur_e):
            eng_end_by_init[name] = we

    rows_staffed = [
        [
            name,
            ("-" if _eff_est(name) is None else f"{_eff_est(name):.1f}"),
            f"{assigned_by_init[name]:.1f}",
            eng_start_by_init.get(name, "-"),
            eng_end_by_init.get(name, "-"),
        ]
        for name in sorted(assigned_by_init.keys())
    ]
    if rows_staffed:
        print_table(
            title,
            ["Initiative", "Required PW", "Assigned PW", "EngStart", "EngEnd"],
            rows_staffed,
        )


def _print_plan_summary(a: DataAdapter, plan_path: str) -> None:
    doc = load_yaml(plan_path)
    assigned: list[Assignment] = []
    for x in doc.get("assignments", []):
        assigned.append(
            Assignment(
                member_name=x.get("member", ""),
                initiative_name=x.get("initiative", ""),
                week_start=x.get("week_start", ""),
                capacity_pw=x.get("capacity_pw"),
            )
        )
    _print_staffed_initiatives(a, assigned, title="Staffed Initiatives (from plan)")
    unstaffed = doc.get("unstaffed", [])
    if unstaffed:
        print_table(
            "Unstaffed Initiatives",
            ["Initiative", "Required PW", "Available PW", "Reason"],
            [
                [
                    x.get("initiative", ""),
                    x.get("required_pw", ""),
                    x.get("available_pw", ""),
                    x.get("reason", ""),
                ]
                for x in unstaffed
            ],
        )


@app.command()
def summary(plan: str) -> None:
    """Summarize an existing plan file (YAML/JSON)."""
    a = get_adapter()
    _print_plan_summary(a, plan)


@app.command()
def plan(
    dfrom: str,
    dto: str,
    algorithm: str = "greedy",
    recreate: bool = typer.Option(False, "--recreate"),
    out: str = typer.Option(..., "--out"),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed planning diagnostics"
    ),
) -> None:
    a = get_adapter()
    pr: GreedyPlanResult | ILPPlanResult | ILPPrefPlanResult
    if verbose:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Planning...", total=None)
            if algorithm == "greedy":
                pr = plan_greedy(
                    a, parse_date(dfrom), parse_date(dto), recreate=recreate
                )
            elif algorithm == "ilp":
                try:
                    pr = plan_ilp(
                        a,
                        parse_date(dfrom),
                        parse_date(dto),
                        recreate=recreate,
                        msg=verbose,
                    )
                except RuntimeError as exc:
                    raise typer.BadParameter(str(exc)) from exc
            elif algorithm == "ilp-pref":
                try:
                    pr = plan_ilp_pref(
                        a,
                        parse_date(dfrom),
                        parse_date(dto),
                        recreate=recreate,
                        msg=verbose,
                    )
                except RuntimeError as exc:
                    raise typer.BadParameter(str(exc)) from exc
            else:
                raise typer.BadParameter("Invalid algorithm. Use 'greedy' or 'ilp'.")
            progress.update(task, description="Finalizing plan...")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Planning...", total=None)
            if algorithm == "greedy":
                pr = plan_greedy(
                    a, parse_date(dfrom), parse_date(dto), recreate=recreate
                )
            elif algorithm == "ilp":
                try:
                    pr = plan_ilp(
                        a,
                        parse_date(dfrom),
                        parse_date(dto),
                        recreate=recreate,
                        msg=verbose,
                    )
                except RuntimeError as exc:
                    raise typer.BadParameter(str(exc)) from exc
            elif algorithm == "ilp-pref":
                try:
                    pr = plan_ilp_pref(
                        a,
                        parse_date(dfrom),
                        parse_date(dto),
                        recreate=recreate,
                        msg=verbose,
                    )
                except RuntimeError as exc:
                    raise typer.BadParameter(str(exc)) from exc
            else:
                raise typer.BadParameter("Invalid algorithm. Use 'greedy' or 'ilp'.")
            progress.update(task, description="Finalizing plan...")
    reason = (
        "PlannerILPPref"
        if algorithm == "ilp-pref"
        else ("PlannerILP" if algorithm == "ilp" else "PlannerGreedy")
    )
    plan_doc = {
        "version": 1,
        "window": {"from": dfrom, "to": dto},
        "algorithm": algorithm,
        "recreate": recreate,
        "summary": pr.summary,
        "assignments": [
            {
                "member": x.member_name,
                "initiative": x.initiative_name,
                "week_start": x.week_start,
                "capacity_pw": x.capacity_pw,
                "reason": reason,
            }
            for x in pr.assignments
        ],
        "unstaffed": pr.unstaffed,
    }
    out_lower = out.lower()
    if out_lower.endswith(".json"):
        save_json(plan_doc, out)
    else:
        # Default to YAML when extension is .yaml/.yml or anything else
        save_yaml(plan_doc, out)
    typer.echo(f"Wrote plan to {out}.")

    # Display staffed initiatives table (required vs assigned, EngStart/End)
    try:
        _print_staffed_initiatives(a, pr.assignments)
    except Exception:
        pass

    if verbose:
        # Show summary table
        t = Table(title="Plan Summary", show_lines=False)
        for col in [
            "initiatives_considered",
            "initiatives_planned",
            "initiatives_unstaffed",
            "total_person_weeks",
        ]:
            t.add_column(col)
        t.add_row(
            str(pr.summary.get("initiatives_considered", "")),
            str(pr.summary.get("initiatives_planned", "")),
            str(pr.summary.get("initiatives_unstaffed", "")),
            str(pr.summary.get("total_person_weeks", "")),
        )
        console.print(t)

        if algorithm == "ilp":
            t2 = Table(title="ILP Diagnostics", show_lines=False)
            for col in [
                "ilp_status",
                "ilp_objective",
                "ilp_solve_seconds",
                "ilp_num_variables",
                "ilp_num_constraints",
                "ilp_x_vars",
                "ilp_member_transition_vars",
                "ilp_week_active_vars",
                "ilp_week_transition_vars",
            ]:
                t2.add_column(col)
            t2.add_row(
                str(pr.summary.get("ilp_status", "")),
                str(pr.summary.get("ilp_objective", "")),
                str(pr.summary.get("ilp_solve_seconds", "")),
                str(pr.summary.get("ilp_num_variables", "")),
                str(pr.summary.get("ilp_num_constraints", "")),
                str(pr.summary.get("ilp_x_vars", "")),
                str(pr.summary.get("ilp_member_transition_vars", "")),
                str(pr.summary.get("ilp_week_active_vars", "")),
                str(pr.summary.get("ilp_week_transition_vars", "")),
            )
            console.print(t2)

            weights = pr.summary.get("weights", {})
            if isinstance(weights, dict):
                t3 = Table(title="ILP Weights", show_lines=False)
                t3.add_column("name")
                t3.add_column("value")
                for k, v in weights.items():
                    t3.add_row(str(k), str(v))
                console.print(t3)

        if pr.unstaffed:
            print_table(
                "Unstaffed Initiatives",
                ["Initiative", "Required PW", "Available PW", "Reason"],
                [
                    [
                        x.get("initiative", ""),
                        x.get("required_pw", ""),
                        x.get("available_pw", ""),
                        x.get("reason", ""),
                    ]
                    for x in pr.unstaffed
                ],
            )


@app.command()
def apply(plan: str, dryrun: bool = typer.Option(False, "--dryrun")) -> None:
    a = get_adapter()
    doc = load_yaml(plan)
    assigned = []
    for x in doc.get("assignments", []):
        assigned.append(
            Assignment(
                member_name=x["member"],
                initiative_name=x["initiative"],
                week_start=x["week_start"],
            )
        )
    if dryrun:
        typer.echo(f"Would create {len(assigned)} assignments.")
        return
    # Provide progress feedback while creating assignments
    total = len(assigned)
    if total == 0:
        typer.echo("No assignments to create.")
        return
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Creating assignments...", total=total)
        batch_size = 25
        for i in range(0, total, batch_size):
            batch = assigned[i : i + batch_size]
            a.upsert_assignments(batch)
            progress.update(task, advance=len(batch))
    typer.echo(f"Created {total} assignments.")
