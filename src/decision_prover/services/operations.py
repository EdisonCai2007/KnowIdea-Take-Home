from ..contracts.context import DecisionContext
from ..contracts.output import OperationStatus, Stage1RunRequest, Stage1RunResponse, Stage2PendingResponse
from ..proposals import ProposalFixture
from ..stage1 import run_stage1


def build_stage1_run_response(
    proposal_fixture: ProposalFixture,
    request: Stage1RunRequest | None = None,
) -> Stage1RunResponse:
    return run_stage1(proposal_fixture, request=request)


def build_stage1_pending_response(proposal_fixture: ProposalFixture) -> Stage1RunResponse:
    return build_stage1_run_response(proposal_fixture)


def build_stage2_pending_response(decision_context: DecisionContext) -> Stage2PendingResponse:
    return Stage2PendingResponse(
        status=OperationStatus(
            state="stage2_pending",
            message="Stage 2 deterministic verifier logic is not implemented in Phase 1.",
        ),
        decision_context=decision_context,
    )
