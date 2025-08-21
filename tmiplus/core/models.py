from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Pool(str, Enum):
    Solutioning = "Solutioning"
    Feature = "Feature"
    Operability = "Operability"
    QA = "QA"


class Phase(str, Enum):
    IdeaDiscovery = "Idea & Discovery"
    Solutioning = "Solutioning"
    Implementation = "Implementation"


class State(str, Enum):
    Open = "Open"
    InProgress = "In progress"
    Blocked = "Blocked"
    Done = "Done"


class BudgetCategory(str, Enum):
    Roadmap = "Roadmap"
    Run = "Run the business"
    TechRefresh = "Tech Refresh"


class Member(BaseModel):
    name: str = Field(..., min_length=1)
    pool: Pool
    contracted_hours: int = Field(default=40, ge=1, le=168)
    squad_label: Optional[str] = None
    active: bool = True
    notes: Optional[str] = None

    @property
    def weekly_capacity_pw(self) -> float:
        return round(self.contracted_hours / 40.0, 3)


class Initiative(BaseModel):
    name: str
    phase: Phase
    state: State
    priority: int = Field(..., ge=1, le=5)
    budget: BudgetCategory
    owner_pools: List[Pool] = Field(default_factory=list)
    required_by: Optional[str] = None  # YYYY-MM-DD
    start_after: Optional[str] = None  # YYYY-MM-DD
    rom_pw: Optional[float] = Field(default=None, ge=0)
    granular_pw: Optional[float] = Field(default=None, ge=0)
    ssot: Optional[str] = None

    @field_validator("owner_pools", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if v is None:
            return []
        return v


class PTOType(str, Enum):
    Holiday = "Holiday"
    Sick = "Sick leave"
    Other = "Other"


class PTORecord(BaseModel):
    member_name: str
    type: PTOType
    week_start: str  # YYYY-MM-DD (Monday)
    week_end: Optional[str] = None  # YYYY-MM-DD (Sunday)
    comment: Optional[str] = None


class AssignmentSource(str, Enum):
    Manual = "Manual"
    PlannerGreedy = "PlannerGreedy"
    PlannerILP = "PlannerILP"


class Assignment(BaseModel):
    member_name: str
    initiative_name: str
    week_start: str  # YYYY-MM-DD (Monday of ISO week)
    source: AssignmentSource = AssignmentSource.Manual
    applied: bool = False
