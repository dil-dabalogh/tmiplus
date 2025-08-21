from __future__ import annotations

import os

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

        self.t_members = Table(api_key, base_id, MEMBERS)
        self.t_inits = Table(api_key, base_id, INITIATIVES)
        self.t_pto = Table(api_key, base_id, PTO)
        self.t_assigns = Table(api_key, base_id, ASSIGNMENTS)

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
        for r in rows:
            f = r.get("fields", {})
            out.append(
                PTORecord(
                    member_name=f.get("MemberName", ""),
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
        for r in rows:
            f = r.get("fields", {})
            out.append(
                Assignment(
                    member_name=f.get("MemberName", ""),
                    initiative_name=f.get("InitiativeName", ""),
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
            if matches:
                self.t_assigns.update(matches[0]["id"], fields)  # type: ignore[arg-type]
            else:
                self.t_assigns.create(fields)  # type: ignore[arg-type]

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
