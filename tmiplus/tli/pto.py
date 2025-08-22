from __future__ import annotations

import typer

from tmiplus.core.models import PTORecord, PTOType
from tmiplus.core.services.csv_io import read_pto_csv, write_pto_csv
from tmiplus.core.util.dates import (
    date_to_str,
    iso_monday,
    iter_weeks,
    parse_date,
    week_end_from_start_str,
)
from tmiplus.tli.context import get_adapter
from tmiplus.tli.helpers import print_table

app = typer.Typer(help="Manage PTO")

# Module-level Typer option singletons to satisfy Ruff B008
NAME_OPT = typer.Option(..., "--name", help="Member name")
FROM_OPT = typer.Option(..., "--from", help="Start Monday (YYYY-MM-DD)")
TO_OPT = typer.Option(..., "--to", help="End Sunday (YYYY-MM-DD)")
PTYPE_OPT = typer.Option(
    ..., "--type", help="PTO type (Holiday, 'Sick leave', Other, 'Public holiday' )"
)
DRYRUN_OPT = typer.Option(False, "--dryrun", help="Show actions without writing")


@app.command(name="list")
def list_cmd() -> None:
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


@app.command()
def create(
    name: str = NAME_OPT,
    dfrom: str = FROM_OPT,
    dto: str = TO_OPT,
    ptype: PTOType = PTYPE_OPT,
    dryrun: bool = DRYRUN_OPT,
) -> None:
    """Create weekly PTO records for a member across a date range.

    The range is inclusive; weeks are generated from the Monday of the start week
    through the Monday of the end week. Each record will have WeekStart set to the
    Monday and WeekEnd set to the corresponding Sunday.
    """
    a = get_adapter()
    start = iso_monday(parse_date(dfrom))
    end = iso_monday(parse_date(dto))
    if start > end:
        raise typer.BadParameter("--from must be on/before --to")

    records: list[PTORecord] = []
    for ws in iter_weeks(start, end):
        ws_str = date_to_str(ws)
        we_str = week_end_from_start_str(ws_str)
        records.append(
            PTORecord(
                member_name=name,
                type=ptype,
                week_start=ws_str,
                week_end=we_str,
            )
        )

    if dryrun:
        typer.echo(
            f"Would create {len(records)} PTO records for {name} of type {ptype.value}."
        )
        return
    if not records:
        typer.echo("No PTO records to create.")
        return
    a.upsert_pto(records)
    typer.echo(f"Created {len(records)} PTO records for {name}.")
