from __future__ import annotations

import typer

from tmiplus.core.models import Pool
from tmiplus.core.services.csv_io import read_members_csv, write_members_csv
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage members")

@app.command()
def list():
    a = get_adapter()
    rows = a.list_members()
    print_table("Members", ["Name","Pool","Hours","Squad","Active"], [
        [m.name, m.pool.value, m.contracted_hours, m.squad_label or "", "Y" if m.active else "N"] for m in rows
    ])

@app.command(name="import")
def import_(path: str = typer.Option(..., "--path")):
    a = get_adapter()
    members = read_members_csv(path)
    a.upsert_members(members)
    typer.echo(f"Imported {len(members)} members.")

@app.command()
def export(out: str = typer.Option(..., "--out")):
    a = get_adapter()
    write_members_csv(out, a.list_members())
    typer.echo(f"Wrote {out}.")

@app.command()
def set_pool(member: str, pool: Pool):
    a = get_adapter()
    ms = a.list_members()
    found = [m for m in ms if m.name == member]
    if not found:
        raise typer.BadParameter(f"Member not found: {member}")
    m = found[0]
    m.pool = pool
    a.upsert_members([m])
    typer.echo(f"Updated pool for {member} -> {pool.value}")
