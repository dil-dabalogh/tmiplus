from __future__ import annotations
import csv
from typing import List
from tmiplus.core.models import Member, Initiative, PTORecord, Assignment, Pool, Phase, State, BudgetCategory, PTOType, AssignmentSource

def read_members_csv(path: str) -> List[Member]:
    out: List[Member] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(Member(
                name=row["Name"].strip(),
                pool=Pool(row["Pool"].strip()),
                contracted_hours=int(row.get("ContractedHours", "40") or "40"),
                squad_label=(row.get("SquadLabel") or "").strip() or None,
                active=(row.get("Active","TRUE").strip().upper() == "TRUE"),
                notes=(row.get("Notes") or "").strip() or None,
            ))
    return out

def write_members_csv(path: str, rows: List[Member]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name","Pool","ContractedHours","SquadLabel","Active","Notes"])
        for m in rows:
            w.writerow([m.name, m.pool.value, m.contracted_hours, m.squad_label or "", "TRUE" if m.active else "FALSE", m.notes or ""])

def read_initiatives_csv(path: str) -> List[Initiative]:
    out: List[Initiative] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            owner_pools = [p.strip() for p in (row.get("OwnerPools","") or "").split(";") if p.strip()]
            out.append(Initiative(
                name=row["Name"].strip(),
                phase=Phase(row["Phase"].strip()),
                state=State(row["State"].strip()),
                priority=int(row["Priority"]),
                budget=BudgetCategory(row["Budget"].strip()),
                owner_pools=[Pool(p) for p in owner_pools],
                required_by=(row.get("RequiredBy") or "").strip() or None,
                start_after=(row.get("StartAfter") or "").strip() or None,
                rom_pw=float(row["ROM_PW"]) if row.get("ROM_PW") else None,
                granular_pw=float(row["Granular_PW"]) if row.get("Granular_PW") else None,
                ssot=(row.get("SSOT") or "").strip() or None,
            ))
    return out

def write_initiatives_csv(path: str, rows: List[Initiative]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name","Phase","State","Priority","Budget","OwnerPools","RequiredBy","StartAfter","ROM_PW","Granular_PW","SSOT"])
        for i in rows:
            pools = ";".join([p.value for p in i.owner_pools])
            w.writerow([i.name, i.phase.value, i.state.value, i.priority, i.budget.value, pools, i.required_by or "", i.start_after or "", i.rom_pw if i.rom_pw is not None else "", i.granular_pw if i.granular_pw is not None else "", i.ssot or ""])

def read_pto_csv(path: str) -> List[PTORecord]:
    out: List[PTORecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(PTORecord(
                member_name=row["MemberName"].strip(),
                type=PTOType(row["Type"].strip()),
                week_start=row["WeekStart"].strip(),
                week_end=(row.get("WeekEnd") or "").strip() or None,
                comment=(row.get("Comment") or "").strip() or None,
            ))
    return out

def write_pto_csv(path: str, rows: List[PTORecord]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["MemberName","Type","WeekStart","WeekEnd","Comment"])
        for p in rows:
            w.writerow([p.member_name, p.type.value, p.week_start, p.week_end or "", p.comment or ""])

def read_assignments_csv(path: str) -> List[Assignment]:
    out: List[Assignment] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(Assignment(
                member_name=row["MemberName"].strip(),
                initiative_name=row["InitiativeName"].strip(),
                week_start=row["WeekStart"].strip(),
                source=AssignmentSource(row.get("Source","Manual").strip() or "Manual"),
            ))
    return out

def write_assignments_csv(path: str, rows: List[Assignment]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["MemberName","InitiativeName","WeekStart","Source"])
        for a in rows:
            src = a.source.value if hasattr(a.source, "value") else str(a.source)
            w.writerow([a.member_name, a.initiative_name, a.week_start, src])
