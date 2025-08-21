from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from tmiplus.adapters.base import DataAdapter
from tmiplus.core.models import Member, Initiative, PTORecord, Assignment


class MemoryAdapter(DataAdapter):
    def __init__(self) -> None:
        self.members: Dict[str, Member] = {}
        self.initiatives: Dict[str, Initiative] = {}
        self.pto: Dict[Tuple[str, str], PTORecord] = {}
        self.assignments: Dict[Tuple[str, str], Assignment] = {}

    # Members
    def list_members(self) -> List[Member]:
        return list(self.members.values())

    def upsert_members(self, members: List[Member]) -> None:
        for m in members:
            self.members[m.name] = m

    def delete_members(self, names: List[str]) -> None:
        for n in names:
            self.members.pop(n, None)

    # Initiatives
    def list_initiatives(self) -> List[Initiative]:
        return list(self.initiatives.values())

    def upsert_initiatives(self, initiatives: List[Initiative]) -> None:
        for i in initiatives:
            self.initiatives[i.name] = i

    def delete_initiatives(self, names: List[str]) -> None:
        for n in names:
            self.initiatives.pop(n, None)

    # PTO
    def list_pto(self) -> List[PTORecord]:
        return list(self.pto.values())

    def upsert_pto(self, pto: List[PTORecord]) -> None:
        for p in pto:
            self.pto[(p.member_name, p.week_start)] = p

    def delete_pto(self, keys: List[Tuple[str, str]]) -> None:
        for k in keys:
            self.pto.pop(k, None)

    # Assignments
    def list_assignments(self) -> List[Assignment]:
        return list(self.assignments.values())

    def upsert_assignments(self, assignments: List[Assignment]) -> None:
        for a in assignments:
            self.assignments[(a.member_name, a.week_start)] = a

    def delete_assignments(self, keys: List[Tuple[str, str]]) -> None:
        for k in keys:
            self.assignments.pop(k, None)

    # Lookups
    def member_by_name(self, name: str) -> Optional[Member]:
        return self.members.get(name)

    def initiative_by_name(self, name: str) -> Optional[Initiative]:
        return self.initiatives.get(name)
