from ..contracts.context import DecisionContext
from ..contracts.output import (
    OperationStatus,
    Stage1Outcome,
    Stage1RunRequest,
    Stage1RunResponse,
    Stage2PendingResponse,
)
from ..contracts.workspace import WorkspaceCompanyProfile
from ..proposals import ProposalFixture
from ..stage1 import (
    continue_stage1_for_workspace_proposal,
    run_stage1,
    run_stage1_for_workspace_proposal,
    skip_stage1_for_workspace_proposal,
)


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


def build_stage2_pending_response(decision_context: DecisionContext) -> Stage2PendingResponse:
    return Stage2PendingResponse(
        status=OperationStatus(
            state="stage2_pending",
            message="Stage 2 deterministic verifier logic is not implemented in Phase 1.",
        ),
        decision_context=decision_context,
    )
