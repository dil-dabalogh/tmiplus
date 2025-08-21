from __future__ import annotations

import json
import os
from urllib import error, request

import typer
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


def _required_schema() -> dict[str, list[str]]:
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


def _check_env() -> tuple[bool, list[tuple[str, str]]]:
    rows: list[tuple[str, str]] = []
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


def _check_airtable_connectivity(a: AirtableAdapter) -> tuple[bool, list[tuple[str, str]]]:  # type: ignore[name-defined]
    results: list[tuple[str, str]] = []
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


def _fetch_airtable_schema_via_meta() -> dict[str, list[str]]:
    """Fetch Airtable base schema using the Metadata API.

    Requires TMI_AIRTABLE_API_KEY and TMI_AIRTABLE_BASE_ID to be set.
    Returns a mapping of table name -> list of field names. On error, returns {}.
    """
    api_key = os.getenv("TMI_AIRTABLE_API_KEY")
    base_id = os.getenv("TMI_AIRTABLE_BASE_ID")
    if not api_key or not base_id:
        return {}
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    req = request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out: dict[str, list[str]] = {}
            for t in data.get("tables", []):
                t_name = t.get("name")
                fields = [f.get("name") for f in t.get("fields", []) if f.get("name")]
                if t_name:
                    out[t_name] = fields
            return out
    except error.HTTPError:
        return {}
    except error.URLError:
        return {}
    except Exception:
        return {}


def _check_airtable_schema(a: AirtableAdapter) -> tuple[bool, list[tuple[str, str]]]:  # type: ignore[name-defined]
    req = _required_schema()
    results: list[tuple[str, str]] = []
    ok = True

    # Prefer Metadata API to inspect field definitions (works even when tables are empty)
    meta = _fetch_airtable_schema_via_meta()
    if meta:
        for table_name, required_fields in req.items():
            actual_fields = set(meta.get(table_name, []))
            if not actual_fields:
                ok = False
                results.append((table_name, "not found in metadata or no fields"))
                continue
            missing = [f for f in required_fields if f not in actual_fields]
            if missing:
                ok = False
                results.append((table_name, f"missing fields: {', '.join(missing)}"))
            else:
                results.append((table_name, "ok"))
        return ok, results

    # Fallback: sample records (may under-report fields when records are empty/sparse)
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
            if not rows:
                results.append((name, "no records; cannot infer fields (consider adding one row)"))
            else:
                missing = [f for f in req[name] if f not in seen]
                if missing:
                    ok = False
                    results.append((name, f"possibly missing fields: {', '.join(missing)} (based on sample records)"))
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


