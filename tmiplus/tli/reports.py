from __future__ import annotations

from datetime import date

import typer

from tmiplus.core.services.reports import budget_distribution, initiative_details
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
    data = budget_distribution(a, f, t)
    total = sum(data.values()) or 1.0
    rows = [[k, f"{v:.2f}", f"{(v/total*100):.1f}%"] for k, v in data.items()]
    print_table("Budget distribution (PW)", ["Category", "PW", "%"], rows)
    # Detailed per-initiative table
    detail = initiative_details(a, f, t)
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
