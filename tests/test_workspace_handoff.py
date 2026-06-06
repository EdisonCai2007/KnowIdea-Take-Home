from __future__ import annotations

import json
from types import SimpleNamespace

from decision_prover.ai.formalization import generate_workspace_formalization
from decision_prover.contracts.output import (
    Stage1CompanyContext,
    Stage1ReadyOutcome,
    Stage1WorkingContext,
    Stage2ProofDraft,
)
from decision_prover.contracts.workspace import WorkspaceCompanyProfile
from decision_prover.services.operations import build_workspace_stage2_handoff
from decision_prover.verifier.proof_draft import validate_stage2_proof_draft


class FakeClient:
    def __init__(self, responses: list[dict[str, object] | str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> SimpleNamespace:
        self.calls.append({"messages": messages, "response_format": response_format})
        if not self._responses:
            raise AssertionError("Unexpected formalization AI call.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        raw_model_response = response if isinstance(response, str) else json.dumps(response)
        return SimpleNamespace(raw_model_response=raw_model_response)


def _ready_result() -> Stage1ReadyOutcome:
    return Stage1ReadyOutcome(
        outcome="stage1_ready",
        proposal_id="WP1",
        proposal="We want to raise our prices by 20% to increase revenue.",
        working_context=Stage1WorkingContext(
            company=Stage1CompanyContext(name="Northwind Software", sector="B2B SaaS"),
            proposal="We want to raise our prices by 20% to increase revenue.",
            decision="Raise prices by 20% for new customers only.",
            objective="Increase revenue while monitoring conversion quality.",
            what_we_know=[
                "The proposal mentions a 20% price increase.",
                "The price change applies to new customers only.",
                "Projected revenue from the new customer cohort is $40,000.",
            ],
            what_still_matters=[],
            constraints_mentioned=["The initiative only works if projected revenue stays above $30,000."],
            success_criteria=["Increase revenue from the new customer cohort."],
            notes=[],
        ),
        readiness_summary="Stage 1 is ready because no additional proof-critical clarification questions remain.",
        completion_reason="no_more_questions",
        unresolved_notes=[],
        transcript=[],
    )


def _proof_payload() -> dict[str, object]:
    return {
        "proof_draft": {
            "claim": "Raising prices by 20% for new customers only keeps projected revenue above the required floor.",
            "premises": [
                {
                    "id": "P1",
                    "statement": "Projected revenue from the new customer cohort is $40,000.",
                    "kind": "fact",
                    "source_locator": "working_context.what_we_know[2]",
                }
            ],
            "computations": [],
            "comparisons": [
                {
                    "id": "K1",
                    "lhs": {"kind": "ref", "value": "P1"},
                    "operator": ">=",
                    "rhs": {"kind": "literal", "value": 30000},
                }
            ],
            "proposed_verdict": "SUPPORTED",
            "refutation_attempt": "The proposal would fail if projected revenue dropped below the stated floor.",
            "unresolved_gaps": [],
        },
        "notes": [],
    }


def test_generate_workspace_formalization_returns_validated_proof_draft() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient([_proof_payload()])

    result = generate_workspace_formalization(
        proposal_id="WP1",
        proposal_text=ready_result.proposal,
        workspace_company=workspace_company,
        ready_result=ready_result,
        answers={"WP1_Q1_1": "new customers only"},
        client=client,
    )

    assert result.status == "formalized"
    assert result.proof_draft.proposed_verdict == "SUPPORTED"
    assert result.validation_report.final_classification == "SUPPORTED"
    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["decision_kernel"]["decision"] == ready_result.working_context.decision
    assert payload["answers"] == [{"question_id": "WP1_Q1_1", "answer": "new customers only"}]
    assert "answer.WP1_Q1_1" in payload["allowed_source_locators"]


def test_build_workspace_stage2_handoff_returns_formalization_error_for_invalid_json() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient(['{"proof_draft": 123}'])

    formalization, verification = build_workspace_stage2_handoff(
        ready_result,
        workspace_company=workspace_company,
        answers={"WP1_Q1_1": "new customers only"},
        client=client,
    )

    assert formalization is not None
    assert formalization.status == "formalization_error"
    assert verification is None


def test_invalid_source_locator_downgrades_workspace_proof_to_undecidable() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient(
        [
            {
                "proof_draft": {
                    "claim": "Projected revenue clears the floor.",
                    "premises": [
                        {
                            "id": "P1",
                            "statement": "Projected revenue from the new customer cohort is $40,000.",
                            "kind": "fact",
                            "source_locator": "working_context.what_we_know[99]",
                        }
                    ],
                    "computations": [],
                    "comparisons": [
                        {
                            "id": "K1",
                            "lhs": {"kind": "ref", "value": "P1"},
                            "operator": ">=",
                            "rhs": {"kind": "literal", "value": 30000},
                        }
                    ],
                    "proposed_verdict": "SUPPORTED",
                    "refutation_attempt": "The claim fails if the floor is higher than expected.",
                    "unresolved_gaps": [],
                },
                "notes": [],
            }
        ]
    )

    formalization, verification = build_workspace_stage2_handoff(
        ready_result,
        workspace_company=workspace_company,
        answers={},
        client=client,
    )

    assert formalization is not None
    assert formalization.status == "formalized"
    assert any(issue.code == "invalid_source_locator" for issue in formalization.validation_report.issues)
    assert verification is not None
    assert verification.classification == "UNDECIDABLE"


def test_result_mismatch_downgrades_supported_model_verdict() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient(
        [
            {
                "proof_draft": {
                    "claim": "Projected revenue clears the floor after discounting half the cohort.",
                    "premises": [
                        {
                            "id": "P1",
                            "statement": "Projected revenue from the new customer cohort is $40,000.",
                            "kind": "fact",
                            "source_locator": "working_context.what_we_know[2]",
                        }
                    ],
                    "computations": [
                        {
                            "id": "C1",
                            "op": "mul",
                            "args": [
                                {"kind": "ref", "value": "P1"},
                                {"kind": "literal", "value": 0.5},
                            ],
                            "result": 15000,
                        }
                    ],
                    "comparisons": [
                        {
                            "id": "K1",
                            "lhs": {"kind": "ref", "value": "C1"},
                            "operator": ">=",
                            "rhs": {"kind": "literal", "value": 10000},
                        }
                    ],
                    "proposed_verdict": "SUPPORTED",
                    "refutation_attempt": "The claim fails if the discounted revenue does not exceed the floor.",
                    "unresolved_gaps": [],
                },
                "notes": [],
            }
        ]
    )

    formalization, verification = build_workspace_stage2_handoff(
        ready_result,
        workspace_company=workspace_company,
        answers={},
        client=client,
    )

    assert formalization is not None
    assert formalization.status == "formalized"
    assert any(issue.code == "result_mismatch" for issue in formalization.validation_report.issues)
    assert formalization.validation_report.downgraded_from_model_verdict is True
    assert verification is not None
    assert verification.classification == "UNDECIDABLE"


def test_duplicate_ids_are_flagged() -> None:
    report = validate_stage2_proof_draft(
        Stage2ProofDraft.model_validate(
            {
                "claim": "Projected revenue clears the floor.",
                "premises": [
                    {
                        "id": "P1",
                        "statement": "Projected revenue from the new customer cohort is $40,000.",
                        "kind": "fact",
                        "source_locator": "working_context.what_we_know[2]",
                    }
                ],
                "computations": [
                    {
                        "id": "P1",
                        "op": "add",
                        "args": [
                            {"kind": "literal", "value": 1},
                            {"kind": "literal", "value": 2},
                        ],
                        "result": 3,
                    }
                ],
                "comparisons": [],
                "proposed_verdict": "UNDECIDABLE",
                "refutation_attempt": "The proof is incomplete.",
                "unresolved_gaps": [],
            }
        ),
        ready_result=_ready_result(),
        answers={},
    )

    assert any(issue.code == "duplicate_id" for issue in report.issues)
    assert report.final_classification == "UNDECIDABLE"


def test_division_by_zero_is_flagged() -> None:
    report = validate_stage2_proof_draft(
        Stage2ProofDraft.model_validate(
            {
                "claim": "Revenue-per-customer ratio remains defined.",
                "premises": [
                    {
                        "id": "P1",
                        "statement": "Projected revenue from the new customer cohort is $40,000.",
                        "kind": "fact",
                        "source_locator": "working_context.what_we_know[2]",
                    }
                ],
                "computations": [
                    {
                        "id": "C1",
                        "op": "div",
                        "args": [
                            {"kind": "ref", "value": "P1"},
                            {"kind": "literal", "value": 0},
                        ],
                        "result": 0,
                    }
                ],
                "comparisons": [],
                "proposed_verdict": "SUPPORTED",
                "refutation_attempt": "The proof fails if the denominator is zero.",
                "unresolved_gaps": [],
            }
        ),
        ready_result=_ready_result(),
        answers={},
    )

    assert any(issue.code == "division_by_zero" for issue in report.issues)
    assert report.final_classification == "UNDECIDABLE"


def test_failed_comparison_yields_refuted_when_no_blocking_issues_remain() -> None:
    report = validate_stage2_proof_draft(
        Stage2ProofDraft.model_validate(
            {
                "claim": "Projected revenue meets the hard floor.",
                "premises": [
                    {
                        "id": "P1",
                        "statement": "Projected revenue from the new customer cohort is $40,000.",
                        "kind": "fact",
                        "source_locator": "working_context.what_we_know[2]",
                    }
                ],
                "computations": [],
                "comparisons": [
                    {
                        "id": "K1",
                        "lhs": {"kind": "ref", "value": "P1"},
                        "operator": "<",
                        "rhs": {"kind": "literal", "value": 30000},
                    }
                ],
                "proposed_verdict": "REFUTED",
                "refutation_attempt": "The floor is violated.",
                "unresolved_gaps": [],
            }
        ),
        ready_result=_ready_result(),
        answers={},
    )

    assert any(issue.code == "comparison_failed" for issue in report.issues)
    assert report.final_classification == "REFUTED"


def test_ambiguous_target_downgrades_otherwise_valid_proof() -> None:
    report = validate_stage2_proof_draft(
        Stage2ProofDraft.model_validate(
            {
                "claim": "The proposal satisfies the stated success criterion.",
                "premises": [
                    {
                        "id": "P1",
                        "statement": "The proposal mentions a 20% price increase.",
                        "kind": "fact",
                        "source_locator": "working_context.what_we_know[0]",
                    },
                    {
                        "id": "T1",
                        "statement": "Higher revenue from new customers.",
                        "kind": "target",
                        "source_locator": "working_context.success_criteria[0]",
                    }
                ],
                "computations": [],
                "comparisons": [
                    {
                        "id": "K1",
                        "lhs": {"kind": "ref", "value": "P1"},
                        "operator": ">=",
                        "rhs": {"kind": "literal", "value": 0.2},
                    }
                ],
                "proposed_verdict": "SUPPORTED",
                "refutation_attempt": "The claim fails if the threshold is not actually binding.",
                "unresolved_gaps": [],
            }
        ),
        ready_result=_ready_result(),
        answers={},
    )

    assert any(issue.code == "ambiguous_target" for issue in report.issues)
    assert report.final_classification == "UNDECIDABLE"
