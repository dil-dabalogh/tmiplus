from __future__ import annotations

import csv

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
from tmiplus.core.util.dates import week_end_from_start_str


def read_members_csv(path: str) -> list[Member]:
    out: list[Member] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                Member(
                    name=row["Name"].strip(),
                    pool=Pool(row["Pool"].strip()),
                    contracted_hours=int(row.get("ContractedHours", "40") or "40"),
                    squad_label=(row.get("SquadLabel") or "").strip() or None,
                    active=(row.get("Active", "TRUE").strip().upper() == "TRUE"),
                    notes=(row.get("Notes") or "").strip() or None,
                )
            )
    return out


def write_members_csv(path: str, rows: list[Member]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name", "Pool", "ContractedHours", "SquadLabel", "Active", "Notes"])
        for m in rows:
            w.writerow(
                [
                    m.name,
                    m.pool.value,
                    m.contracted_hours,
                    m.squad_label or "",
                    "TRUE" if m.active else "FALSE",
                    m.notes or "",
                ]
            )


def read_initiatives_csv(path: str) -> list[Initiative]:
    out: list[Initiative] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            owner_pools = [
                p.strip()
                for p in (row.get("OwnerPools", "") or "").split(";")
                if p.strip()
            ]
            out.append(
                Initiative(
                    name=row["Name"].strip(),
                    phase=Phase(row["Phase"].strip()),
                    state=State(row["State"].strip()),
                    priority=int(row["Priority"]),
                    budget=BudgetCategory(row["Budget"].strip()),
                    owner_pools=[Pool(p) for p in owner_pools],
                    required_by=(row.get("RequiredBy") or "").strip() or None,
                    start_after=(row.get("StartAfter") or "").strip() or None,
                    rom_pw=(
                        float(row.get("ROM") or row.get("ROM_PW"))
                        if (row.get("ROM") or row.get("ROM_PW"))
                        else None
                    ),
                    granular_pw=(
                        float(row.get("Granular") or row.get("Granular_PW"))
                        if (row.get("Granular") or row.get("Granular_PW"))
                        else None
                    ),
                    ssot=(row.get("SSOT") or "").strip() or None,
                )
            )
    return out


def write_initiatives_csv(path: str, rows: list[Initiative]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
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
            ]
        )
        for i in rows:
            pools = ";".join([p.value for p in i.owner_pools])
            w.writerow(
                [
                    i.name,
                    i.phase.value,
                    i.state.value,
                    i.priority,
                    i.budget.value,
                    pools,
                    i.required_by or "",
                    i.start_after or "",
                    i.rom_pw if i.rom_pw is not None else "",
                    i.granular_pw if i.granular_pw is not None else "",
                    i.ssot or "",
                ]
            )


def read_pto_csv(path: str) -> list[PTORecord]:
    out: list[PTORecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                PTORecord(
                    member_name=row["MemberName"].strip(),
                    type=PTOType(row["Type"].strip()),
                    week_start=row["WeekStart"].strip(),
                    week_end=(row.get("WeekEnd") or "").strip() or None,
                    comment=(row.get("Comment") or "").strip() or None,
                )
            )
    return out


def write_pto_csv(path: str, rows: list[PTORecord]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["MemberName", "Type", "WeekStart", "WeekEnd", "Comment"])
        for p in rows:
            w.writerow(
                [
                    p.member_name,
                    p.type.value,
                    p.week_start,
                    p.week_end or "",
                    p.comment or "",
                ]
            )


def read_assignments_csv(path: str) -> list[Assignment]:
    out: list[Assignment] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ws = row["WeekStart"].strip()
            we = (row.get("WeekEnd") or "").strip() or None
            out.append(
                Assignment(
                    member_name=row["MemberName"].strip(),
                    initiative_name=row["InitiativeName"].strip(),
                    week_start=ws,
                    week_end=we or week_end_from_start_str(ws),
                )
            )
    return out


def write_assignments_csv(path: str, rows: list[Assignment]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["MemberName", "InitiativeName", "WeekStart", "WeekEnd"])
        for a in rows:
            w.writerow(
                [
                    a.member_name,
                    a.initiative_name,
                    a.week_start,
                    a.week_end or week_end_from_start_str(a.week_start),
                ]
            )
