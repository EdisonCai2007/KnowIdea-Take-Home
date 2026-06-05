from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..proposals import ProposalPrompt
from .battery import StatedAssumption
from .context import DecisionContext


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Classification(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    UNDECIDABLE = "UNDECIDABLE"


class DerivationStep(StrictModel):
    rule: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: Any


class BindingConstraintResult(StrictModel):
    id: str = Field(min_length=1)
    passed: bool = Field(
        validation_alias=AliasChoices("pass", "passed"),
        serialization_alias="pass",
    )
    why: str = Field(min_length=1)


class RefutationResult(StrictModel):
    attempted: bool
    failure_conditions: str | None = None


class VerificationResult(StrictModel):
    classification: Classification
    derivation: list[DerivationStep] = Field(default_factory=list)
    binding_constraints: list[BindingConstraintResult] = Field(default_factory=list)
    load_bearing_assumptions: list[StatedAssumption] = Field(default_factory=list)
    refutation: RefutationResult
    pivotal_assumption: str | None = None
    flip_threshold: Any | None = None


class OperationStatus(StrictModel):
    state: Literal["stage1_pending", "stage2_pending"]
    message: str = Field(min_length=1)


class ProposalRunResponse(StrictModel):
    status: OperationStatus
    proposals: list[ProposalPrompt] = Field(default_factory=list)


class Stage2PendingResponse(StrictModel):
    status: OperationStatus
    decision_context: DecisionContext


class ValidationSummary(StrictModel):
    status: Literal["ok"]
    companies: int = Field(ge=0)
    decisions: int = Field(ge=0)
    decision_contexts: int = Field(ge=0)
