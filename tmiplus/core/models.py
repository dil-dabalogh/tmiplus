from __future__ import annotations

from enum import Enum

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
    squad_label: str | None = None
    active: bool = True
    notes: str | None = None

    @property
    def weekly_capacity_pw(self) -> float:
        return round(self.contracted_hours / 40.0, 3)


class Initiative(BaseModel):
    name: str
    phase: Phase
    state: State
    priority: int = Field(..., ge=1, le=5)
    budget: BudgetCategory
    owner_pools: list[Pool] = Field(default_factory=list)
    required_by: str | None = None  # YYYY-MM-DD
    start_after: str | None = None  # YYYY-MM-DD
    rom_pw: float | None = Field(default=None, ge=0)
    granular_pw: float | None = Field(default=None, ge=0)
    ssot: str | None = None

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
    week_end: str | None = None  # YYYY-MM-DD (Sunday)
    comment: str | None = None


class Assignment(BaseModel):
    member_name: str
    initiative_name: str
    week_start: str  # YYYY-MM-DD (Monday of ISO week)
    week_end: str | None = None  # YYYY-MM-DD (Sunday of ISO week)
