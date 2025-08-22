from __future__ import annotations

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from tmiplus.core.models import Pool
from tmiplus.core.services.csv_io import read_members_csv, write_members_csv
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage members")


@app.command()
def list() -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching members...", total=None)
        rows = a.list_members()
        progress.update(task, description="Rendering table...")
    print_table(
        "Members",
        ["Name", "Pool", "Hours", "Squad", "Active"],
        [
            [
                m.name,
                m.pool.value,
                str(m.contracted_hours),
                m.squad_label or "",
                "Y" if m.active else "N",
            ]
            for m in rows
        ],
    )


@app.command(name="import")
def import_(path: str = typer.Option(..., "--path")) -> None:
    a = get_adapter()
    members = read_members_csv(path)
    total = len(members)
    if total == 0:
        typer.echo("No members to import.")
        return
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Importing members...", total=total)
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = members[i : i + batch_size]
            a.upsert_members(batch)
            progress.update(task, advance=len(batch))
    typer.echo(f"Imported {total} members.")


@app.command()
def export(out: str = typer.Option(..., "--out")) -> None:
    a = get_adapter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching members...", total=None)
        rows = a.list_members()
        progress.update(task, description="Writing CSV...")
        write_members_csv(out, rows)
    typer.echo(f"Wrote {out}.")


@app.command()
def set_pool(member: str, pool: Pool) -> None:
    a = get_adapter()
    ms = a.list_members()
    found = [m for m in ms if m.name == member]
    if not found:
        raise typer.BadParameter(f"Member not found: {member}")
    m = found[0]
    m.pool = pool
    a.upsert_members([m])
    typer.echo(f"Updated pool for {member} -> {pool.value}")
