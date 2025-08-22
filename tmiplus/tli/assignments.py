from __future__ import annotations

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tmiplus.core.models import Assignment
from tmiplus.core.services.csv_io import read_assignments_csv, write_assignments_csv
from tmiplus.core.services.planner_greedy import PlanResult as GreedyPlanResult
from tmiplus.core.services.planner_greedy import plan_greedy
from tmiplus.core.services.planner_ilp import PlanResult as ILPPlanResult
from tmiplus.core.services.planner_ilp import plan_ilp
from tmiplus.core.util.dates import parse_date
from tmiplus.core.util.io import load_yaml, save_json, save_yaml
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

console = Console()

app = typer.Typer(help="Manage assignments")


@app.command()
def list() -> None:
    a = get_adapter()
    rows = a.list_assignments()
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
    a.upsert_assignments(items)
    typer.echo(f"Imported {len(items)} assignments.")


@app.command()
def export(out: str = typer.Option(..., "--out")) -> None:
    a = get_adapter()
    write_assignments_csv(out, a.list_assignments())
    typer.echo(f"Wrote {out}.")


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
    pr: GreedyPlanResult | ILPPlanResult
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
            else:
                raise typer.BadParameter("Invalid algorithm. Use 'greedy' or 'ilp'.")
            progress.update(task, description="Finalizing plan...")
    else:
        if algorithm == "greedy":
            pr = plan_greedy(a, parse_date(dfrom), parse_date(dto), recreate=recreate)
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
        else:
            raise typer.BadParameter("Invalid algorithm. Use 'greedy' or 'ilp'.")
    reason = "PlannerILP" if algorithm == "ilp" else "PlannerGreedy"
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
    a.upsert_assignments(assigned)
    typer.echo(f"Created {len(assigned)} assignments.")
