from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

import typer
from rich.console import Console

# Third-party/standard imports above; internal imports below
from tmiplus.tli.assignments import app as assignments_app
from tmiplus.tli.config_cmd import app as config_app
from tmiplus.tli.health import app as health_app
from tmiplus.tli.initiatives import app as initiatives_app
from tmiplus.tli.members import app as members_app
from tmiplus.tli.pto import app as pto_app
from tmiplus.tli.reports import app as reports_app

app = typer.Typer(add_completion=False)
console = Console()

app.add_typer(members_app, name="members")
app.add_typer(initiatives_app, name="initiatives")
app.add_typer(pto_app, name="pto")
app.add_typer(assignments_app, name="assignments")
app.add_typer(reports_app, name="reports")
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")

def _version_callback(value: bool):
    if value:
        try:
            console.print(f"tmiplus {pkg_version('tmiplus')}")
        except PackageNotFoundError:  # pragma: no cover
            console.print("tmiplus (version unknown)")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(  # type: ignore[assignment]
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        is_eager=True,
        callback=_version_callback,
    )
):
    """TMI Resource Planning CLI"""

@app.command()
def version():
    """Show version."""
    try:
        console.print(f"tmiplus {pkg_version('tmiplus')}")
    except PackageNotFoundError:  # pragma: no cover
        console.print("tmiplus (version unknown)")
