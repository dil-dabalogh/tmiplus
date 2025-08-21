from __future__ import annotations
import typer, os
from rich.console import Console
from tmiplus.adapters.memory.adapter import MemoryAdapter
from tmiplus.adapters.airtable.adapter import AirtableAdapter

app = typer.Typer(add_completion=False)
console = Console()

# Subcommands
from tmiplus.tli.members import app as members_app
from tmiplus.tli.initiatives import app as initiatives_app
from tmiplus.tli.pto import app as pto_app
from tmiplus.tli.assignments import app as assignments_app
from tmiplus.tli.reports import app as reports_app
from tmiplus.tli.config_cmd import app as config_app

app.add_typer(members_app, name="members")
app.add_typer(initiatives_app, name="initiatives")
app.add_typer(pto_app, name="pto")
app.add_typer(assignments_app, name="assignments")
app.add_typer(reports_app, name="reports")
app.add_typer(config_app, name="config")

def _get_adapter():
    # If Airtable env vars exist, use Airtable; else Memory
    if os.getenv("TMI_AIRTABLE_API_KEY") and os.getenv("TMI_AIRTABLE_BASE_ID"):
        return AirtableAdapter()
    return MemoryAdapter()

@app.callback()
def main():
    """TMI Resource Planning CLI"""

@app.command()
def version():
    """Show version."""
    console.print("tmiplus 0.1.0")

def get_adapter():
    return _get_adapter()
