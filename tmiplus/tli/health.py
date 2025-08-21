from __future__ import annotations
import os
import typer
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from tmiplus.tli.context import get_adapter

try:
    # Optional import for isinstance checks
    from tmiplus.adapters.airtable.adapter import AirtableAdapter
except Exception:  # pragma: no cover - optional
    AirtableAdapter = object  # type: ignore

app = typer.Typer(help="Health checks for environment, connectivity, and schema")
console = Console()


def _required_schema() -> Dict[str, List[str]]:
    return {
        "Members": ["Name", "Pool", "ContractedHours", "SquadLabel", "Active", "Notes"],
        "Initiatives": [
            "Name",
            "Phase",
            "State",
            "Priority",
            "Budget",
            "OwnerPools",
            "RequiredBy",
            "StartAfter",
            "ROM",
            "Granular",
            "SSOT",
        ],
        "PTO": ["MemberName", "Type", "WeekStart", "WeekEnd", "Comment"],
        "Assignments": ["MemberName", "InitiativeName", "WeekStart", "WeekEnd"],
    }


def _check_env() -> Tuple[bool, List[Tuple[str, str]]]:
    rows: List[Tuple[str, str]] = []
    ok = True
    for key in ["TMI_AIRTABLE_API_KEY", "TMI_AIRTABLE_BASE_ID"]:
        val = os.getenv(key)
        status = "set" if val else "missing"
        if key == "TMI_AIRTABLE_API_KEY":
            shown = (val[:4] + "…") if val else ""
        else:
            shown = (val[:6] + "…") if val else ""
        rows.append((key, status if status == "missing" else f"set ({shown})"))
        if status == "missing":
            ok = False
    return ok, rows


def _check_airtable_connectivity(a: AirtableAdapter) -> Tuple[bool, List[Tuple[str, str]]]:  # type: ignore[name-defined]
    results: List[Tuple[str, str]] = []
    ok = True
    for name, table in [
        ("Members", a.t_members),
        ("Initiatives", a.t_inits),
        ("PTO", a.t_pto),
        ("Assignments", a.t_assigns),
    ]:
        try:
            _ = table.all(max_records=1)
            results.append((name, "ok"))
        except Exception as e:
            ok = False
            results.append((name, f"error: {type(e).__name__}"))
    return ok, results


def _check_airtable_schema(a: AirtableAdapter) -> Tuple[bool, List[Tuple[str, str]]]:  # type: ignore[name-defined]
    req = _required_schema()
    results: List[Tuple[str, str]] = []
    ok = True
    # Best-effort: union field keys from up to a few records; if no records, report unknown
    for name, table in [
        ("Members", a.t_members),
        ("Initiatives", a.t_inits),
        ("PTO", a.t_pto),
        ("Assignments", a.t_assigns),
    ]:
        try:
            rows = table.all(max_records=5)
            seen: set[str] = set()
            for r in rows:
                fields = r.get("fields", {}) or {}
                seen.update(fields.keys())
            missing = [f for f in req[name] if f not in seen]
            if rows and missing:
                ok = False
                results.append((name, f"missing fields: {', '.join(missing)}"))
            elif not rows:
                # Could not infer; provide required list
                results.append((name, f"no records; required: {', '.join(req[name])}"))
            else:
                results.append((name, "ok"))
        except Exception as e:
            ok = False
            results.append((name, f"error: {type(e).__name__}"))
    return ok, results


@app.command()
def check() -> None:
    """Run environment, connectivity, and schema checks."""
    adapter = get_adapter()

    # Env check (relevant for Airtable)
    env_ok, env_rows = _check_env()
    env_table = Table(title="Environment variables")
    env_table.add_column("Variable")
    env_table.add_column("Status")
    for k, v in env_rows:
        env_table.add_row(k, v)
    console.print(env_table)

    # Adapter-specific checks
    if isinstance(adapter, AirtableAdapter):  # type: ignore[arg-type]
        conn_ok, conn_rows = _check_airtable_connectivity(adapter)  # type: ignore[arg-type]
        conn_table = Table(title="Connectivity (Airtable)")
        conn_table.add_column("Table")
        conn_table.add_column("Status")
        for k, v in conn_rows:
            conn_table.add_row(k, v)
        console.print(conn_table)

        schema_ok, schema_rows = _check_airtable_schema(adapter)  # type: ignore[arg-type]
        schema_table = Table(title="Schema (Airtable)")
        schema_table.add_column("Table")
        schema_table.add_column("Status")
        for k, v in schema_rows:
            schema_table.add_row(k, v)
        console.print(schema_table)

        overall = env_ok and conn_ok and schema_ok
    else:
        # Memory adapter: trivial checks
        info = Table(title="Adapter: Memory")
        info.add_column("Check")
        info.add_column("Status")
        info.add_row("Connectivity", "ok")
        info.add_row("Schema", "in-memory (implicit)")
        console.print(info)
        overall = True

    if not overall:
        raise typer.Exit(code=1)
    console.print("All checks passed.")


