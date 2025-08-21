from __future__ import annotations

import os
from typing import Any, cast

from pyairtable import Table

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import (
    Assignment,
    BudgetCategory,
    Initiative,
    Member,
    Phase,
    Pool,
    PTORecord,
    PTOType,
    State,
)

MEMBERS = "Members"
INITIATIVES = "Initiatives"
PTO = "PTO"
ASSIGNMENTS = "Assignments"


class AirtableAdapter(DataAdapter):
    def __init__(self) -> None:
        api_key = os.getenv("TMI_AIRTABLE_API_KEY")
        base_id = os.getenv("TMI_AIRTABLE_BASE_ID")
        if not api_key or not base_id:
            raise RuntimeError("Missing TMI_AIRTABLE_API_KEY or TMI_AIRTABLE_BASE_ID")
        self._api_key = api_key
        self._base_id = base_id

        self.t_members = Table(api_key, base_id, MEMBERS)
        self.t_inits = Table(api_key, base_id, INITIATIVES)
        self.t_pto = Table(api_key, base_id, PTO)
        self.t_assigns = Table(api_key, base_id, ASSIGNMENTS)

        # Detected or configured mapping for linked field names in Assignments table
        # Prefer reading schema from Airtable meta API; fall back to record probing.
        self.assign_member_link_field = os.getenv("TMI_ASSIGN_MEMBER_LINK_FIELD")
        self.assign_initiative_link_field = os.getenv(
            "TMI_ASSIGN_INITIATIVE_LINK_FIELD"
        )
        # Allow creating records without links (not recommended). Defaults to False.
        self.assign_allow_minimal = (
            os.getenv("TMI_ASSIGN_ALLOW_MINIMAL", "false").strip().lower() == "true"
        )
        # Try to detect via schema (requires PAT with schema scope); ignore errors
        self._detect_assignment_link_fields_schema()

    # --------- Members
    def list_members(self) -> list[Member]:
        rows = self.t_members.all()
        out: list[Member] = []
        for r in rows:
            f = r.get("fields", {})
            out.append(
                Member(
                    name=f.get("Name", ""),
                    pool=Pool(f.get("Pool")),
                    contracted_hours=int(f.get("ContractedHours", 40)),
                    squad_label=f.get("SquadLabel"),
                    active=bool(f.get("Active", True)),
                    notes=f.get("Notes"),
                )
            )
        return out

    def upsert_members(self, members: list[Member]) -> None:
        for m in members:
            matches = self.t_members.all(formula=f"{{Name}}='{m.name}'")
            fields: dict[str, str | int | float | bool | None] = {
                "Name": m.name,
                "Pool": m.pool.value,
                "ContractedHours": m.contracted_hours,
                "SquadLabel": m.squad_label or "",
                "Active": m.active,
                "Notes": m.notes or "",
            }
            if matches:
                self.t_members.update(matches[0]["id"], fields)  # type: ignore[arg-type]
            else:
                self.t_members.create(fields)  # type: ignore[arg-type]

    def delete_members(self, names: list[str]) -> None:
        for n in names:
            matches = self.t_members.all(formula=f"{{Name}}='{n}'")
            for r in matches:
                self.t_members.delete(r["id"])

    # --------- Initiatives
    def list_initiatives(self) -> list[Initiative]:
        rows = self.t_inits.all()
        out: list[Initiative] = []
        for r in rows:
            f = r.get("fields", {})
            owner_pools = f.get("OwnerPools", [])
            if isinstance(owner_pools, str):
                owner_pools = [owner_pools]
            out.append(
                Initiative(
                    name=f.get("Name", ""),
                    phase=Phase(f.get("Phase")),
                    state=State(f.get("State")),
                    priority=int(f.get("Priority", 3)),
                    budget=BudgetCategory(f.get("Budget")),
                    owner_pools=[Pool(p) for p in owner_pools if p],
                    required_by=f.get("RequiredBy"),
                    start_after=f.get("StartAfter"),
                    rom_pw=(
                        f.get("ROM") if f.get("ROM") is not None else f.get("ROM_PW")
                    ),
                    granular_pw=(
                        f.get("Granular")
                        if f.get("Granular") is not None
                        else f.get("Granular_PW")
                    ),
                    ssot=f.get("SSOT"),
                )
            )
        return out

    def upsert_initiatives(self, initiatives: list[Initiative]) -> None:
        for i in initiatives:
            matches = self.t_inits.all(formula=f"{{Name}}='{i.name}'")
            fields: dict[str, str | int | float | bool | list[str] | None] = {
                "Name": i.name,
                "Phase": i.phase.value,
                "State": i.state.value,
                "Priority": i.priority,
                "Budget": i.budget.value,
                "OwnerPools": [p.value for p in i.owner_pools],
                "RequiredBy": i.required_by or None,
                "StartAfter": i.start_after or None,
                # Prefer new column name 'ROM'; fall back to legacy 'ROM_PW' for compatibility
                "ROM": i.rom_pw,
                # Prefer new column name 'Granular'; fall back to legacy 'Granular_PW' for compatibility
                "Granular": i.granular_pw,
                "SSOT": i.ssot or None,
            }
            if matches:
                self.t_inits.update(matches[0]["id"], fields)  # type: ignore[arg-type]
            else:
                self.t_inits.create(fields)  # type: ignore[arg-type]

    def delete_initiatives(self, names: list[str]) -> None:
        for n in names:
            matches = self.t_inits.all(formula=f"{{Name}}='{n}'")
            for r in matches:
                self.t_inits.delete(r["id"])

    # --------- PTO
    def list_pto(self) -> list[PTORecord]:
        rows = self.t_pto.all()
        out: list[PTORecord] = []

        def _first_str(value: object) -> str:
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                first = value[0]
                return str(first) if isinstance(first, str | int | float) else ""
            return ""

        for r in rows:
            f = r.get("fields", {})
            out.append(
                PTORecord(
                    member_name=_first_str(f.get("MemberName", "")),
                    type=PTOType(f.get("Type")),
                    week_start=f.get("WeekStart", ""),
                    week_end=f.get("WeekEnd"),
                    comment=f.get("Comment"),
                )
            )
        return out

    def upsert_pto(self, pto: list[PTORecord]) -> None:
        for p in pto:
            matches = self.t_pto.all(
                formula=f"AND({{MemberName}}='{p.member_name}', {{WeekStart}}='{p.week_start}')"
            )
            fields: dict[str, str | int | float | bool | None] = {
                "MemberName": p.member_name,
                "Type": p.type.value,
                "WeekStart": p.week_start,
                "WeekEnd": p.week_end or None,
                "Comment": p.comment or None,
            }
            if matches:
                self.t_pto.update(matches[0]["id"], fields)  # type: ignore[arg-type]
            else:
                self.t_pto.create(fields)  # type: ignore[arg-type]

    def delete_pto(self, keys: list[tuple[str, str]]) -> None:
        for member_name, week_start in keys:
            matches = self.t_pto.all(
                formula=f"AND({{MemberName}}='{member_name}', {{WeekStart}}='{week_start}')"
            )
            for r in matches:
                self.t_pto.delete(r["id"])

    # --------- Assignments
    def list_assignments(self) -> list[Assignment]:
        rows = self.t_assigns.all()
        out: list[Assignment] = []

        def _first_str(value: object) -> str:
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                first = value[0]
                return str(first) if isinstance(first, str | int | float) else ""
            return ""

        for r in rows:
            f = r.get("fields", {})
            out.append(
                Assignment(
                    member_name=_first_str(f.get("MemberName", "")),
                    initiative_name=_first_str(f.get("InitiativeName", "")),
                    week_start=f.get("WeekStart", ""),
                    week_end=f.get("WeekEnd"),
                )
            )
        return out

    def upsert_assignments(self, assignments: list[Assignment]) -> None:
        for a in assignments:
            matches = self.t_assigns.all(
                formula=f"AND({{MemberName}}='{a.member_name}', {{WeekStart}}='{a.week_start}')"
            )
            fields: dict[str, str | int | float | bool | None] = {
                "MemberName": a.member_name,
                "InitiativeName": a.initiative_name,
                "WeekStart": a.week_start,
                "WeekEnd": a.week_end or None,
            }
            try:
                if matches:
                    self.t_assigns.update(matches[0]["id"], fields)  # type: ignore[arg-type]
                else:
                    self.t_assigns.create(fields)  # type: ignore[arg-type]
            except Exception as exc:
                # Fallback for bases where MemberName/InitiativeName are computed fields.
                # In that case, write using linked fields instead (Member/Initiative)
                msg = str(exc)
                if "INVALID_VALUE_FOR_COLUMN" in msg and (
                    "MemberName" in msg or "InitiativeName" in msg
                ):
                    # Determine link fields strictly via schema (no probing fallback)
                    self._detect_assignment_link_fields_schema()
                    m_field = self.assign_member_link_field
                    i_field = self.assign_initiative_link_field
                    if not (m_field and i_field):
                        raise RuntimeError(
                            "Assignments upsert failed: could not determine linked field names from Airtable schema. "
                            "Ensure your API token has meta schema access and the Assignments table contains "
                            "linked fields to Members and Initiatives."
                        ) from exc

                    # First try linking by names with typecast
                    try:
                        name_link_fields: dict[str, object] = {
                            m_field: [a.member_name],
                            i_field: [a.initiative_name],
                            "WeekStart": a.week_start,
                            "WeekEnd": a.week_end or None,
                        }
                        if matches:
                            self.t_assigns.update(
                                matches[0]["id"],
                                cast(dict[str, Any], name_link_fields),
                                typecast=True,
                            )
                        else:
                            self.t_assigns.create(
                                cast(dict[str, Any], name_link_fields), typecast=True
                            )
                        continue
                    except Exception:
                        # Fallback to linking by record IDs
                        member_id = self._member_record_id_by_name(a.member_name)
                        init_id = self._initiative_record_id_by_name(a.initiative_name)
                        if not (member_id and init_id):
                            raise
                        id_link_fields: dict[str, object] = {
                            m_field: [{"id": member_id}],
                            i_field: [{"id": init_id}],
                            "WeekStart": a.week_start,
                            "WeekEnd": a.week_end or None,
                        }
                        if matches:
                            self.t_assigns.update(
                                matches[0]["id"], cast(dict[str, Any], id_link_fields)
                            )
                        else:
                            self.t_assigns.create(cast(dict[str, Any], id_link_fields))
                        continue

    def _detect_assignment_link_fields(self) -> None:
        """Attempt to infer the Assignments table linked field names by inspecting existing records.

        Heuristic: find fields whose values are lists of record ids (strings starting with 'rec') or
        list of objects with an 'id' that looks like a record id. Then, for the first record id in
        each such field, try fetching it from Members and Initiatives tables to determine which is which.
        """
        if self.assign_member_link_field and self.assign_initiative_link_field:
            return
        try:
            rows = self.t_assigns.all(max_records=10)
        except Exception:
            return
        if not rows:
            return
        candidate_fields: set[str] = set()
        for r in rows:
            f = r.get("fields", {})
            for k, v in f.items():
                if isinstance(v, list) and v:
                    first = v[0]
                    rec_id: str | None = None
                    if isinstance(first, str) and first.startswith("rec"):
                        rec_id = first
                    elif (
                        isinstance(first, dict)
                        and isinstance(first.get("id"), str)
                        and str(first["id"]).startswith("rec")
                    ):
                        rec_id = str(first["id"])
                    if rec_id:
                        candidate_fields.add(k)
        # Try to classify candidates by dereferencing one id
        for field_name in candidate_fields:
            # find a sample id for this field from the rows
            sample_id: str | None = None
            for r in rows:
                vals = r.get("fields", {}).get(field_name)
                if isinstance(vals, list) and vals:
                    first = vals[0]
                    if isinstance(first, str):
                        sample_id = first
                    elif isinstance(first, dict):
                        sid = first.get("id")
                        if isinstance(sid, str):
                            sample_id = sid
                if sample_id:
                    break
            if not sample_id:
                continue
            is_member = False
            is_initiative = False
            try:
                self.t_members.get(sample_id)
                is_member = True
            except Exception:
                pass
            try:
                self.t_inits.get(sample_id)
                is_initiative = True
            except Exception:
                pass
            if is_member and not self.assign_member_link_field:
                self.assign_member_link_field = field_name
            if is_initiative and not self.assign_initiative_link_field:
                self.assign_initiative_link_field = field_name
            if self.assign_member_link_field and self.assign_initiative_link_field:
                break

    def _detect_assignment_link_fields_schema(self) -> None:
        """Use Airtable meta API to determine the linked field names for Assignments.

        This requires API token with schema scope. If unavailable, silently skip.
        """
        if self.assign_member_link_field and self.assign_initiative_link_field:
            return
        try:
            import requests as _rq  # type: ignore[import-untyped]

            url = f"https://api.airtable.com/v0/meta/bases/{self._base_id}/tables"
            headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = _rq.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return
            data = resp.json()
            tables = data.get("tables", [])
            assigns_tbl = next(
                (t for t in tables if t.get("name") == ASSIGNMENTS), None
            )
            if not assigns_tbl:
                return
            # Build tableId->name mapping
            table_id_to_name = {t.get("id"): t.get("name") for t in tables}
            member_field: str | None = None
            init_field: str | None = None
            for f in assigns_tbl.get("fields", []):
                if f.get("type") != "multipleRecordLinks":
                    continue
                link = f.get("options", {}).get("linkedTableId")
                if not isinstance(link, str):
                    continue
                linked_name = table_id_to_name.get(link)
                if linked_name == MEMBERS and not member_field:
                    member_field = f.get("name")
                if linked_name == INITIATIVES and not init_field:
                    init_field = f.get("name")
            if member_field and init_field:
                self.assign_member_link_field = member_field
                self.assign_initiative_link_field = init_field
        except Exception:
            return

    def delete_assignments(self, keys: list[tuple[str, str]]) -> None:
        for member_name, week_start in keys:
            matches = self.t_assigns.all(
                formula=f"AND({{MemberName}}='{member_name}', {{WeekStart}}='{week_start}')"
            )
            for r in matches:
                self.t_assigns.delete(r["id"])

    # --------- Lookups
    def member_by_name(self, name: str) -> Member | None:
        matches = self.t_members.all(formula=f"{{Name}}='{name}'")
        if not matches:
            return None
        # fetch fresh
        rows = self.t_members.all(formula=f"{{Name}}='{name}'")
        if not rows:
            return None
        f = rows[0].get("fields", {})
        return Member(
            name=f.get("Name", ""),
            pool=Pool(f.get("Pool")),
            contracted_hours=int(f.get("ContractedHours", 40)),
            squad_label=f.get("SquadLabel"),
            active=bool(f.get("Active", True)),
            notes=f.get("Notes"),
        )

    def _member_record_id_by_name(self, name: str) -> str | None:
        matches = self.t_members.all(formula=f"{{Name}}='{name}'")
        if not matches:
            return None
        rid = matches[0].get("id")
        return str(rid) if isinstance(rid, str) else None

    def initiative_by_name(self, name: str) -> Initiative | None:
        matches = self.t_inits.all(formula=f"{{Name}}='{name}'")
        if not matches:
            return None
        f = matches[0].get("fields", {})
        owner_pools = f.get("OwnerPools", [])
        if isinstance(owner_pools, str):
            owner_pools = [owner_pools]
        return Initiative(
            name=f.get("Name", ""),
            phase=Phase(f.get("Phase")),
            state=State(f.get("State")),
            priority=int(f.get("Priority", 3)),
            budget=BudgetCategory(f.get("Budget")),
            owner_pools=[Pool(p) for p in owner_pools if p],
            required_by=f.get("RequiredBy"),
            start_after=f.get("StartAfter"),
            rom_pw=f.get("ROM") if f.get("ROM") is not None else f.get("ROM_PW"),
            granular_pw=(
                f.get("Granular")
                if f.get("Granular") is not None
                else f.get("Granular_PW")
            ),
            ssot=f.get("SSOT"),
        )

    def _initiative_record_id_by_name(self, name: str) -> str | None:
        matches = self.t_inits.all(formula=f"{{Name}}='{name}'")
        if not matches:
            return None
        rid = matches[0].get("id")
        return str(rid) if isinstance(rid, str) else None
