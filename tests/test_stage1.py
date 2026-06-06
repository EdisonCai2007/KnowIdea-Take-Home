from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from decision_prover.contracts.output import Stage1RunRequest
from decision_prover.contracts.workspace import WorkspaceCompanyProfile
from decision_prover.fixtures import load_proposals_fixture
from decision_prover.stage1 import (
    Stage1ExecutionError,
    canonicalize_company_id,
    continue_stage1_for_workspace_proposal,
    run_stage1,
    run_stage1_for_workspace_proposal,
    skip_stage1_for_workspace_proposal,
)


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
            raise AssertionError("Unexpected Stage 1 AI call.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        raw_model_response = response if isinstance(response, str) else json.dumps(response)
        return SimpleNamespace(raw_model_response=raw_model_response)


def _load_fixture(proposals_path: Path):
    return load_proposals_fixture(proposals_path)


def _working_context(
    *,
    decision: str = "Raise prices by 20% for part of the customer base.",
    objective: str = "Increase revenue while preserving conversion quality.",
    what_we_know: list[str] | None = None,
    what_still_matters: list[str] | None = None,
) -> dict[str, object]:
    return {
        "working_context": {
            "company": {
                "name": "Northwind Software",
                "sector": "B2B SaaS",
            },
            "proposal": "We want to raise our prices by 20% to increase revenue.",
            "decision": decision,
            "objective": objective,
            "what_we_know": what_we_know or ["The proposal mentions a 20% price increase."],
            "what_still_matters": what_still_matters or ["Which customers the price change applies to."],
            "constraints_mentioned": [],
            "success_criteria": ["Higher revenue from the affected segment."],
            "notes": [],
        }
    }


def _question_batch() -> dict[str, object]:
    return {
        "questions": [
            {
                "prompt": "Who exactly would this price change apply to?",
                "rationale": "I need the affected customer scope to tighten the decision brief.",
                "suggested_answers": [
                    {"label": "All customers", "value": "all customers"},
                    {"label": "New customers only", "value": "new customers only"},
                    {"label": "Existing customers only", "value": "existing customers only"},
                ],
                "recommended_answer_index": 1,
            }
        ]
    }


def _empty_question_batch() -> dict[str, object]:
    return {"questions": []}


def test_stage1_workspace_start_returns_clarification_needed() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient([_working_context(), _question_batch()])

    result = run_stage1_for_workspace_proposal(
        proposal_id="WP1",
        proposal_text="We want to raise our prices by 20% to increase revenue.",
        workspace_company=workspace_company,
        client=client,
    )

    assert result.outcome == "clarification_needed"
    assert result.working_context.company.name == "Northwind Software"
    assert result.questions[0].prompt == "Who exactly would this price change apply to?"
    assert result.questions[0].recommended_answer_index == 1


def test_stage1_workspace_answer_loop_returns_stage1_ready() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient(
        [
            _working_context(),
            _question_batch(),
            _working_context(
                what_we_know=[
                    "The proposal mentions a 20% price increase.",
                    "The price change applies to new customers only.",
                ],
                what_still_matters=[],
            ),
            _empty_question_batch(),
        ]
    )

    initial = run_stage1_for_workspace_proposal(
        proposal_id="WP1",
        proposal_text="We want to raise our prices by 20% to increase revenue.",
        workspace_company=workspace_company,
        client=client,
    )
    result = continue_stage1_for_workspace_proposal(
        initial,
        answers={"WP1_Q1_1": "new customers only"},
        workspace_company=workspace_company,
        client=client,
    )

    assert result.outcome == "stage1_ready"
    assert result.completion_reason == "no_more_questions"
    update_payload = json.loads(client.calls[2]["messages"][1]["content"])
    assert update_payload["answers"] == [
        {
            "question_id": "WP1_Q1_1",
            "prompt": "Who exactly would this price change apply to?",
            "answer": "new customers only",
        }
    ]


def test_stage1_skip_returns_ready_with_unresolved_notes() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient([_working_context(), _question_batch()])

    initial = run_stage1_for_workspace_proposal(
        proposal_id="WP1",
        proposal_text="We want to raise our prices by 20% to increase revenue.",
        workspace_company=workspace_company,
        client=client,
    )
    skipped = skip_stage1_for_workspace_proposal(initial)

    assert skipped.outcome == "stage1_ready"
    assert skipped.completion_reason == "user_continue"
    assert skipped.unresolved_notes
    assert skipped.transcript[-1].kind == "ready"


def test_stage1_batch_run_supports_skip_remaining(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_working_context(), _question_batch()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(proposal_ids=["P5"], skip_remaining=True),
        client=client,
    )

    assert response.results[0].outcome == "stage1_ready"
    assert response.results[0].completion_reason == "user_continue"


def test_stage1_rejects_invalid_initial_context_json(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient(['{"working_context": 123}'])

    with pytest.raises(Stage1ExecutionError, match="initial context JSON"):
        run_stage1(proposal_fixture, Stage1RunRequest(proposal_ids=["P1"]), client=client)


def test_stage1_workspace_payload_excludes_description() -> None:
    workspace_company = WorkspaceCompanyProfile(
        name="Northwind Software",
        sector="B2B SaaS",
        description="Should not be sent to Stage 1 AI.",
    )
    client = FakeClient([_working_context(), _question_batch()])

    run_stage1_for_workspace_proposal(
        proposal_id="WP2",
        proposal_text="We want to raise our prices by 20% to boost revenue.",
        workspace_company=workspace_company,
        client=client,
    )

    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["workspace_company"] == {
        "name": "Northwind Software",
        "sector": "B2B SaaS",
    }


def test_canonicalize_company_id_uses_kebab_case() -> None:
    assert canonicalize_company_id("Lumen Labs") == "lumen-labs"
    assert canonicalize_company_id("Northwind  Software!") == "northwind-software"
