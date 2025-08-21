from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_POOLS = ["Solutioning", "Feature", "Operability", "QA"]

class PlannerWeights(BaseModel):
    priority_base: int = 1
    priority_map: dict[int, int] = Field(default_factory=lambda: {1:5, 2:4, 3:3, 4:2, 5:1})
    deadline_penalty_per_week: float = 0.1

class PlannerConfig(BaseModel):
    default_algorithm: str = "greedy"
    weights: PlannerWeights = PlannerWeights()
    squad_policy: str = "all_or_none"

class ReportingConfig(BaseModel):
    include_unassigned: bool = True

class RootConfig(BaseModel):
    pools: list[str] = Field(default_factory=lambda: DEFAULT_POOLS.copy())
    planner: PlannerConfig = PlannerConfig()
    reporting: ReportingConfig = ReportingConfig()
