from __future__ import annotations

from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Assignment, Initiative, Member, PTORecord


class MemoryAdapter(DataAdapter):
    def __init__(self) -> None:
        self.members: dict[str, Member] = {}
        self.initiatives: dict[str, Initiative] = {}
        self.pto: dict[tuple[str, str], PTORecord] = {}
        self.assignments: dict[tuple[str, str], Assignment] = {}

    # Members
    def list_members(self) -> list[Member]:
        return list(self.members.values())

    def upsert_members(self, members: list[Member]) -> None:
        for m in members:
            self.members[m.name] = m

    def delete_members(self, names: list[str]) -> None:
        for n in names:
            self.members.pop(n, None)

    # Initiatives
    def list_initiatives(self) -> list[Initiative]:
        return list(self.initiatives.values())

    def upsert_initiatives(self, initiatives: list[Initiative]) -> None:
        for i in initiatives:
            self.initiatives[i.name] = i

    def delete_initiatives(self, names: list[str]) -> None:
        for n in names:
            self.initiatives.pop(n, None)

    # PTO
    def list_pto(self) -> list[PTORecord]:
        return list(self.pto.values())

    def upsert_pto(self, pto: list[PTORecord]) -> None:
        for p in pto:
            self.pto[(p.member_name, p.week_start)] = p

    def delete_pto(self, keys: list[tuple[str, str]]) -> None:
        for k in keys:
            self.pto.pop(k, None)

    # Assignments
    def list_assignments(self) -> list[Assignment]:
        return list(self.assignments.values())

    def upsert_assignments(self, assignments: list[Assignment]) -> None:
        for a in assignments:
            self.assignments[(a.member_name, a.week_start)] = a

    def delete_assignments(self, keys: list[tuple[str, str]]) -> None:
        for k in keys:
            self.assignments.pop(k, None)

    # Lookups
    def member_by_name(self, name: str) -> Member | None:
        return self.members.get(name)

    def initiative_by_name(self, name: str) -> Initiative | None:
        return self.initiatives.get(name)
