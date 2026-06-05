from ..contracts.context import DecisionContext
from ..contracts.output import OperationStatus, ProposalRunResponse, Stage2PendingResponse
from ..proposals import ProposalFixture


def build_stage1_pending_response(proposal_fixture: ProposalFixture) -> ProposalRunResponse:
    return ProposalRunResponse(
        status=OperationStatus(
            state="stage1_pending",
            message="Stage 1 interview and formalization logic is not implemented in Phase 1.",
        ),
        proposals=proposal_fixture.proposals,
    )


def build_stage2_pending_response(decision_context: DecisionContext) -> Stage2PendingResponse:
    return Stage2PendingResponse(
        status=OperationStatus(
            state="stage2_pending",
            message="Stage 2 deterministic verifier logic is not implemented in Phase 1.",
        ),
        decision_context=decision_context,
    )

