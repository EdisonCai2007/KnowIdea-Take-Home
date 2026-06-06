from typing import Any

from ..ai import WorkspaceFormalizationExecutionError, generate_workspace_formalization
from ..contracts.context import DecisionContext
from ..contracts.output import (
    OperationStatus,
    Stage1Outcome,
    Stage1RunRequest,
    Stage1RunResponse,
    Stage2FormalizationError,
    Stage2FormalizationOutcome,
    Stage2PendingResponse,
    VerificationResult,
)
from ..contracts.workspace import WorkspaceCompanyProfile
from ..proposals import ProposalFixture
from ..settings import ConfigurationError
from ..stage1 import (
    continue_stage1_for_workspace_proposal,
    run_stage1,
    run_stage1_for_workspace_proposal,
    skip_stage1_for_workspace_proposal,
)
from ..verifier.proof_draft import build_proof_verification_result


def build_stage1_run_response(
    proposal_fixture: ProposalFixture,
    request: Stage1RunRequest | None = None,
) -> Stage1RunResponse:
    return run_stage1(proposal_fixture, request=request)


def build_stage1_pending_response(proposal_fixture: ProposalFixture) -> Stage1RunResponse:
    return build_stage1_run_response(proposal_fixture)


def build_workspace_stage1_result(
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
) -> Stage1Outcome:
    return run_stage1_for_workspace_proposal(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
    )


def continue_workspace_stage1_result(
    result: Stage1Outcome,
    *,
    answers: dict[str, str],
    workspace_company: WorkspaceCompanyProfile,
) -> Stage1Outcome:
    if result.outcome != "clarification_needed":
        return result
    return continue_stage1_for_workspace_proposal(
        result=result,
        answers=answers,
        workspace_company=workspace_company,
    )


def skip_workspace_stage1_result(result: Stage1Outcome) -> Stage1Outcome:
    if result.outcome != "clarification_needed":
        return result
    return skip_stage1_for_workspace_proposal(result)


def build_workspace_stage2_handoff(
    result: Stage1Outcome,
    *,
    workspace_company: WorkspaceCompanyProfile,
    answers: dict[str, str],
    settings: Any | None = None,
    client: Any | None = None,
) -> tuple[Stage2FormalizationOutcome | None, VerificationResult | None]:
    if result.outcome != "stage1_ready":
        return None, None

    formalization: Stage2FormalizationOutcome
    try:
        success = generate_workspace_formalization(
            proposal_id=result.proposal_id,
            proposal_text=result.proposal,
            workspace_company=workspace_company,
            ready_result=result,
            answers=answers,
            settings=settings,
            client=client,
        )
        verification_result = build_proof_verification_result(
            success.proof_draft,
            success.validation_report,
        )
        return success, verification_result
    except (ConfigurationError, WorkspaceFormalizationExecutionError) as exc:
        if "success" in locals():
            proof_draft = success.proof_draft
            validation_report = success.validation_report
            notes = success.notes
        else:
            proof_draft = None
            validation_report = None
            notes = []
        formalization = Stage2FormalizationError(
            status="formalization_error",
            message=str(exc),
            proof_draft=proof_draft,
            validation_report=validation_report,
            notes=notes,
        )
        return formalization, None


def build_stage2_pending_response(decision_context: DecisionContext) -> Stage2PendingResponse:
    return Stage2PendingResponse(
        status=OperationStatus(
            state="stage2_pending",
            message="Stage 2 deterministic verifier logic is not implemented in Phase 1.",
        ),
        decision_context=decision_context,
    )
