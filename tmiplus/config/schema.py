from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_POOLS = ["Solutioning", "Feature", "Operability", "QA"]


class PlannerWeights(BaseModel):
    priority_base: int = 1
    priority_map: dict[int, int] = Field(
        default_factory=lambda: {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
    )
    deadline_penalty_per_week: float = 0.1


class IlpWeights(BaseModel):
    # Soft preferences to encourage compact, low-fragmentation plans
    early_week_bonus: float = 0.25
    member_chunk_transition_penalty: float = 2.0
    init_span_transition_penalty: float = 1.0
    init_active_week_penalty: float = 0.25
    complete_priority_weight: float = 1000.0


class IlpConfig(BaseModel):
    # Solver
    time_limit_s: int | None = 120
    mip_gap: float | None = 0.01
    threads: int | None = 0
    # Objective weights
    weights: IlpWeights = IlpWeights()


class PlannerConfig(BaseModel):
    default_algorithm: str = "greedy"
    weights: PlannerWeights = PlannerWeights()
    squad_policy: str = "all_or_none"
    ilp: IlpConfig = IlpConfig()


class ReportingConfig(BaseModel):
    include_unassigned: bool = True


class RootConfig(BaseModel):
    pools: list[str] = Field(default_factory=lambda: DEFAULT_POOLS.copy())
    planner: PlannerConfig = PlannerConfig()
    reporting: ReportingConfig = ReportingConfig()
