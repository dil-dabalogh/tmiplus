from __future__ import annotations
import typer
from tmiplus.core.services.csv_io import read_initiatives_csv, write_initiatives_csv
from tmiplus.tli.__main__ import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage initiatives")

@app.command()
def list():
    a = get_adapter()
    rows = a.list_initiatives()
    print_table("Initiatives", ["Name","Phase","State","Priority","Budget","OwnerPools"], [
        [i.name, i.phase.value, i.state.value, i.priority, i.budget.value, ",".join([p.value for p in i.owner_pools])] for i in rows
    ])

@app.command()
def import_(path: str = typer.Option(..., "--path")):
    a = get_adapter()
    items = read_initiatives_csv(path)
    a.upsert_initiatives(items)
    typer.echo(f"Imported {len(items)} initiatives.")

@app.command()
def export(out: str = typer.Option(..., "--out")):
    a = get_adapter()
    write_initiatives_csv(out, a.list_initiatives())
    typer.echo(f"Wrote {out}.")
