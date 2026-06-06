from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

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


class Stage1CompanyContext(StrictModel):
    name: str | None = None
    sector: str | None = None


class Stage1WorkingContext(StrictModel):
    company: Stage1CompanyContext
    proposal: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    what_we_know: list[str] = Field(default_factory=list)
    what_still_matters: list[str] = Field(default_factory=list)
    constraints_mentioned: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Stage1SuggestedAnswer(StrictModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)


class Stage1Question(StrictModel):
    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    suggested_answers: list[Stage1SuggestedAnswer] = Field(min_length=3, max_length=3)
    recommended_answer_index: int = Field(ge=0, le=2)
    allow_custom_answer: Literal[True] = True


class Stage1TranscriptTurn(StrictModel):
    speaker: Literal["assistant", "user"]
    kind: Literal["answer", "continue", "note", "proposal", "question", "ready"]
    text: str = Field(min_length=1)
    question_id: str | None = None


class ClarificationNeededOutcome(StrictModel):
    outcome: Literal["clarification_needed"]
    proposal_id: str = Field(min_length=1)
    proposal: str = Field(min_length=1)
    working_context: Stage1WorkingContext
    questions: list[Stage1Question] = Field(min_length=1, max_length=3)
    transcript: list[Stage1TranscriptTurn] = Field(default_factory=list)


class Stage1ReadyOutcome(StrictModel):
    outcome: Literal["stage1_ready"]
    proposal_id: str = Field(min_length=1)
    proposal: str = Field(min_length=1)
    working_context: Stage1WorkingContext
    readiness_summary: str = Field(min_length=1)
    completion_reason: Literal["no_more_questions", "user_continue", "max_rounds"]
    unresolved_notes: list[str] = Field(default_factory=list)
    transcript: list[Stage1TranscriptTurn] = Field(default_factory=list)


Stage1Outcome = Annotated[
    ClarificationNeededOutcome | Stage1ReadyOutcome,
    Field(discriminator="outcome"),
]


class Stage1RunRequest(StrictModel):
    proposal_ids: list[str] = Field(default_factory=list)
    answers: dict[str, dict[str, str]] = Field(default_factory=dict)
    skip_remaining: bool = False


class Stage1RunResponse(StrictModel):
    status: OperationStatus
    title: str = Field(min_length=1)
    results: list[Stage1Outcome] = Field(default_factory=list)


ProposalRunResponse = Stage1RunResponse


class Stage2PendingResponse(StrictModel):
    status: OperationStatus
    decision_context: DecisionContext


class GroundingEntry(StrictModel):
    field: str = Field(min_length=1)
    source_type: Literal["workspace", "proposal", "answer", "stage1_summary"]
    source_quote: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)


class GroundingReport(StrictModel):
    entries: list[GroundingEntry] = Field(default_factory=list)


class Stage2ProofPremise(StrictModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    kind: Literal["fact", "assumption", "target"]
    source_locator: str = Field(min_length=1)


class Stage2ProofRefOperand(StrictModel):
    kind: Literal["ref"]
    value: str = Field(min_length=1)


class Stage2ProofLiteralOperand(StrictModel):
    kind: Literal["literal"]
    value: int | float

    @field_validator("value", mode="before")
    @classmethod
    def reject_bool_literal(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("literal operands must be numeric")
        return value


Stage2ProofOperand = Annotated[
    Stage2ProofRefOperand | Stage2ProofLiteralOperand,
    Field(discriminator="kind"),
]


class Stage2ProofComputation(StrictModel):
    id: str = Field(min_length=1)
    op: Literal["add", "sub", "mul", "div"]
    args: list[Stage2ProofOperand] = Field(min_length=2)
    result: int | float

    @field_validator("result", mode="before")
    @classmethod
    def reject_bool_result(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("computation results must be numeric")
        return value


class Stage2ProofComparison(StrictModel):
    id: str = Field(min_length=1)
    lhs: Stage2ProofOperand
    operator: Literal["<", "<=", ">", ">=", "=="]
    rhs: Stage2ProofOperand


class Stage2ProofDraft(StrictModel):
    claim: str = Field(min_length=1)
    premises: list[Stage2ProofPremise] = Field(default_factory=list)
    computations: list[Stage2ProofComputation] = Field(default_factory=list)
    comparisons: list[Stage2ProofComparison] = Field(default_factory=list)
    proposed_verdict: Classification
    refutation_attempt: str = Field(min_length=1)
    unresolved_gaps: list[str] = Field(default_factory=list)


class Stage2ProofValidationIssue(StrictModel):
    code: Literal[
        "unknown_reference",
        "duplicate_id",
        "invalid_source_locator",
        "unsupported_operation",
        "invalid_operand_type",
        "division_by_zero",
        "result_mismatch",
        "comparison_failed",
        "ambiguous_target",
        "ungrounded_premise",
        "load_bearing_gap",
    ]
    message: str = Field(min_length=1)
    subject_id: str | None = None


class Stage2ProofValidationReport(StrictModel):
    accepted: bool
    issues: list[Stage2ProofValidationIssue] = Field(default_factory=list)
    checked_premise_ids: list[str] = Field(default_factory=list)
    checked_computation_ids: list[str] = Field(default_factory=list)
    checked_comparison_ids: list[str] = Field(default_factory=list)
    final_classification: Classification
    downgraded_from_model_verdict: bool


class NormalizedAction(StrictModel):
    statement: str = Field(min_length=1)
    type: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class NormalizedFact(StrictModel):
    key: str = Field(min_length=1)
    value: str | int | float | bool
    unit: str = Field(min_length=1)
    statement: str = Field(min_length=1)


class NormalizedGatingCondition(StrictModel):
    statement: str = Field(min_length=1)
    kind: Literal["hard_constraint", "gating_threshold"]
    semi_formal: str | None = None
    metric_key: str | None = None
    operator: str | None = None
    value: str | int | float | bool | None = None
    unit: str | None = None
    action_field_hint: str | None = None


class NormalizedAssumption(StrictModel):
    statement: str = Field(min_length=1)
    status: Literal["given", "projected"]


class NormalizedFeasibilityBundle(StrictModel):
    action: NormalizedAction
    facts: list[NormalizedFact] = Field(default_factory=list)
    gating_conditions: list[NormalizedGatingCondition] = Field(default_factory=list)
    assumptions: list[NormalizedAssumption] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Stage2FormalizationSuccess(StrictModel):
    status: Literal["formalized"]
    proof_draft: Stage2ProofDraft
    validation_report: Stage2ProofValidationReport
    notes: list[str] = Field(default_factory=list)


class Stage2FormalizationError(StrictModel):
    status: Literal["formalization_error"]
    message: str = Field(min_length=1)
    proof_draft: Stage2ProofDraft | None = None
    validation_report: Stage2ProofValidationReport | None = None
    notes: list[str] = Field(default_factory=list)


Stage2FormalizationOutcome = Annotated[
    Stage2FormalizationSuccess | Stage2FormalizationError,
    Field(discriminator="status"),
]


class ValidationSummary(StrictModel):
    status: Literal["ok"]
    companies: int = Field(ge=0)
    decisions: int = Field(ge=0)
    decision_contexts: int = Field(ge=0)
