from __future__ import annotations

from datetime import date

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from tmiplus.core.services.reports import (
    budget_distribution,
    idle_capacity,
    initiative_details,
    pto_breakdown,
)
from tmiplus.core.util.dates import parse_date
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Reports")


def current_quarter_dates(today: date) -> tuple[date, date]:
    q = (today.month - 1) // 3 + 1
    start_month = 3 * (q - 1) + 1
    start = date(today.year, start_month, 1)
    # end is last day of third month
    end_month = start_month + 2
    if end_month in (1, 3, 5, 7, 8, 10, 12):
        end_day = 31
    elif end_month == 2:
        # naive (non-leap compensation ok for report default)
        end_day = 29 if today.year % 4 == 0 else 28
    else:
        end_day = 30
    end = date(today.year, end_month, end_day)
    return (start, end)


@app.command("budget-distribution")
def budget_distribution_cmd(
    dfrom: str = typer.Option(None, "--from"), dto: str = typer.Option(None, "--to")
) -> None:
    a = get_adapter()
    if dfrom and dto:
        f, t = parse_date(dfrom), parse_date(dto)
    else:
        f, t = current_quarter_dates(date.today())
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Computing budget distribution...", total=None)
        data = budget_distribution(a, f, t)
        progress.update(task, description="Preparing tables...")
    total = sum(data.values()) or 1.0
    rows = [[k, f"{v:.2f}", f"{(v/total*100):.1f}%"] for k, v in data.items()]
    print_table("Budget distribution (PW)", ["Category", "PW", "%"], rows)
    # Detailed per-initiative table
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task2 = progress.add_task("Computing initiative details...", total=None)
        detail = initiative_details(a, f, t)
        progress.update(task2, description="Rendering tables...")
    if detail:
        rows2 = [
            [
                d["name"],
                d["budget"],
                (
                    f"{d['estimate_pw']:.1f}"
                    if isinstance(d["estimate_pw"], int | float)
                    else "-"
                ),
                d["estimate_type"],
                f"{d['assigned_pw']:.2f}",
            ]
            for d in detail
        ]
        print_table(
            "Initiative allocation (PW)",
            ["Initiative", "Budget", "Estimate PW", "Type", "Assigned PW"],
            rows2,
        )
    # PTO breakdown by type
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task3 = progress.add_task("Computing PTO breakdown...", total=None)
        pto = pto_breakdown(a, f, t)
        progress.update(task3, description="Rendering tables...")
    if pto:
        rows3 = [[k, f"{v:.2f}"] for k, v in pto.items()]
        print_table("PTO by type (PW)", ["Type", "PW"], rows3)


@app.command("idle")
def idle_cmd(
    dfrom: str = typer.Option(..., "--from"), dto: str = typer.Option(..., "--to")
) -> None:
    a = get_adapter()
    f, t = parse_date(dfrom), parse_date(dto)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Computing idle capacity...", total=None)
        rows = idle_capacity(a, f, t)
        progress.update(task, description="Rendering table...")
    print_table(
        "Idle capacity (PW)",
        ["Member", "Idle PW"],
        [[r["name"], f"{r['idle_pw']:.2f}"] for r in rows],
    )
