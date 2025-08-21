from __future__ import annotations

import typer

from tmiplus.core.services.csv_io import read_pto_csv, write_pto_csv
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage PTO")


@app.command()
def list() -> None:
    a = get_adapter()
    rows = a.list_pto()
    print_table(
        "PTO",
        ["Member", "Type", "WeekStart", "WeekEnd"],
        [[p.member_name, p.type.value, p.week_start, p.week_end or ""] for p in rows],
    )


@app.command(name="import")
def import_(path: str = typer.Option(..., "--path")) -> None:
    a = get_adapter()
    items = read_pto_csv(path)
    a.upsert_pto(items)
    typer.echo(f"Imported {len(items)} PTO records.")


@app.command()
def export(out: str = typer.Option(..., "--out")) -> None:
    a = get_adapter()
    write_pto_csv(out, a.list_pto())
    typer.echo(f"Wrote {out}.")
