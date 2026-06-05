from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .actions import ActionPayload
from .battery import CompanyFact, Constraint, StatedAssumption


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompanyContext(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    facts: dict[str, CompanyFact] = Field(default_factory=dict)
    constraints: list[Constraint] = Field(default_factory=list)


class DecisionContext(StrictModel):
    id: str = Field(min_length=1)
    company: CompanyContext
    proposal: str = Field(min_length=1)
    action: ActionPayload
    objective: str = Field(min_length=1)
    stated_assumptions: list[StatedAssumption] = Field(default_factory=list)


class DecisionContextList(RootModel[list[DecisionContext]]):
    pass

