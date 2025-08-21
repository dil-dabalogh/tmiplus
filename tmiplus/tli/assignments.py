from __future__ import annotations

import typer

from tmiplus.core.models import Assignment
from tmiplus.core.services.csv_io import read_assignments_csv, write_assignments_csv
from tmiplus.core.services.planner_greedy import plan_greedy
from tmiplus.core.util.dates import parse_date
from tmiplus.core.util.io import load_yaml, save_json, save_yaml
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage assignments")


@app.command()
def list() -> None:
    a = get_adapter()
    rows = a.list_assignments()
    print_table(
        "Assignments",
        ["Member", "Initiative", "WeekStart", "WeekEnd"],
        [
            [x.member_name, x.initiative_name, x.week_start, x.week_end or ""]
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
) -> None:
    a = get_adapter()
    if algorithm != "greedy":
        raise typer.BadParameter("Only 'greedy' implemented in prototype.")

    pr = plan_greedy(a, parse_date(dfrom), parse_date(dto), recreate=recreate)
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
                "capacity_pw": None,
                "reason": "PlannerGreedy",
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
