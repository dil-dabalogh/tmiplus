from __future__ import annotations

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from tmiplus.core.services.csv_io import read_initiatives_csv, write_initiatives_csv
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage initiatives")


@app.command()
def list() -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching initiatives...", total=None)
        rows = a.list_initiatives()
        progress.update(task, description="Rendering table...")
    print_table(
        "Initiatives",
        ["Name", "Phase", "State", "Priority", "Budget", "OwnerPools"],
        [
            [
                i.name,
                i.phase.value,
                i.state.value,
                str(i.priority),
                i.budget.value,
                ",".join([p.value for p in i.owner_pools]),
            ]
            for i in rows
        ],
    )


@app.command(name="import")
def import_(path: str = typer.Option(..., "--path")) -> None:
    a = get_adapter()
    items = read_initiatives_csv(path)
    total = len(items)
    if total == 0:
        typer.echo("No initiatives to import.")
        return
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Importing initiatives...", total=total)
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = items[i : i + batch_size]
            a.upsert_initiatives(batch)
            progress.update(task, advance=len(batch))
    typer.echo(f"Imported {total} initiatives.")


@app.command()
def export(out: str = typer.Option(..., "--out")) -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching initiatives...", total=None)
        rows = a.list_initiatives()
        progress.update(task, description="Writing CSV...")
        write_initiatives_csv(out, rows)
    typer.echo(f"Wrote {out}.")
