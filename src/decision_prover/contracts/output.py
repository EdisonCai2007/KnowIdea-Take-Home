from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .battery import DecisionBattery, StatedAssumption
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
    supported_if: str | None = None
    refuted_if: str | None = None


class AiIndependentNote(StrictModel):
    topic: str = Field(min_length=1)
    note: str = Field(min_length=1)


class AiIndependentResult(StrictModel):
    classification: Classification
    summary: str = Field(min_length=1)
    notes: list[AiIndependentNote] = Field(default_factory=list)


class ExplainDiagnostics(StrictModel):
    stage: Literal["success", "provider", "parse"]
    provider_response_json: dict[str, Any] | None = None
    response_id: str | None = None
    response_model: str | None = None
    provider: str | None = None
    system_fingerprint: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    openrouter_metadata: dict[str, Any] | None = None
    http_status: int | None = None
    parsed_ai_result: AiIndependentResult | None = None


class VerificationExplainResponse(StrictModel):
    result: VerificationResult
    ai_status: Literal["generated", "error"]
    comparison: Literal["match", "mismatch", "ai_error"]
    model: str | None = None
    ai_result: AiIndependentResult | None = None
    message: str | None = None
    diagnostics: ExplainDiagnostics | None = None


class OperationStatus(StrictModel):
    state: Literal["stage1_complete", "stage1_pending", "stage2_pending"]
    message: str = Field(min_length=1)


class Stage1Gap(StrictModel):
    id: str = Field(min_length=1)
    category: Literal[
        "action_details",
        "company_fact",
        "company_metadata",
        "hard_constraint",
        "objective",
        "scope",
    ]
    field: str = Field(min_length=1)
    verification_check: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Stage1Question(StrictModel):
    id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    question: str = Field(min_length=1)
    verification_check: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class Stage1TranscriptTurn(StrictModel):
    speaker: Literal["assistant", "user"]
    kind: Literal["answer", "formalization", "note", "proposal", "question"]
    text: str = Field(min_length=1)
    question_id: str | None = None


class ClarificationNeededOutcome(StrictModel):
    outcome: Literal["clarification_needed"]
    proposal_id: str = Field(min_length=1)
    proposal: str = Field(min_length=1)
    scope_status: Literal["supported_family", "unsupported_family", "ambiguous_family"]
    action_type: str | None = None
    objective: str | None = None
    blocking_fields: list[str] = Field(default_factory=list)
    gaps: list[Stage1Gap] = Field(default_factory=list)
    questions: list[Stage1Question] = Field(default_factory=list)
    ignored_details: list[str] = Field(default_factory=list)
    transcript: list[Stage1TranscriptTurn] = Field(default_factory=list)


class GroundingReportEntry(StrictModel):
    field: str = Field(min_length=1)
    source_type: Literal["proposal", "answer"]
    source_quote: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)


class GroundingReport(StrictModel):
    entries: list[GroundingReportEntry] = Field(default_factory=list)


class FormalizedOutcome(StrictModel):
    outcome: Literal["formalized"]
    proposal_id: str = Field(min_length=1)
    proposal: str = Field(min_length=1)
    battery_document: DecisionBattery
    primary_decision_id: str = Field(min_length=1)
    grounding_report: GroundingReport
    ignored_details: list[str] = Field(default_factory=list)
    transcript: list[Stage1TranscriptTurn] = Field(default_factory=list)


Stage1Outcome = Annotated[
    ClarificationNeededOutcome | FormalizedOutcome,
    Field(discriminator="outcome"),
]


class Stage1RunRequest(StrictModel):
    proposal_ids: list[str] = Field(default_factory=list)
    answers: dict[str, dict[str, str]] = Field(default_factory=dict)


class Stage1RunResponse(StrictModel):
    status: OperationStatus
    title: str = Field(min_length=1)
    results: list[Stage1Outcome] = Field(default_factory=list)


ProposalRunResponse = Stage1RunResponse


class Stage2PendingResponse(StrictModel):
    status: OperationStatus
    decision_context: DecisionContext


class ValidationSummary(StrictModel):
    status: Literal["ok"]
    companies: int = Field(ge=0)
    decisions: int = Field(ge=0)
    decision_contexts: int = Field(ge=0)
