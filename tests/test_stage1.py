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


def _fact(value: int | float | str, unit: str) -> dict[str, object]:
    return {"value": value, "unit": unit}


def _constraint(constraint_id: str, statement: str, semi_formal: str) -> dict[str, object]:
    return {
        "id": constraint_id,
        "kind": "hard",
        "statement": statement,
        "semi_formal": semi_formal,
    }


def _e(
    field: str,
    quote: str,
    *,
    source_type: str = "proposal",
    source_locator: str = "proposal",
) -> dict[str, str]:
    return {
        "field": field,
        "source_type": source_type,
        "source_quote": quote,
        "source_locator": source_locator,
    }


def _parse_output(
    *,
    action_family: str | None = "price_change",
    scope_status: str = "supported_family",
    company_name: str | None = "Northwind Software",
    sector: str | None = "B2B SaaS",
    scope: str | None = None,
    include_scope_evidence: bool = False,
) -> dict[str, object]:
    evidence = [
        _e("companies[0].name", company_name or "Northwind Software"),
        _e("companies[0].sector", sector or "B2B SaaS"),
        _e("decisions[0].action.type", "raise our prices by 20%"),
        _e("decisions[0].action.pct_increase", "20%"),
        _e("decisions[0].objective", "increase revenue"),
    ]
    if include_scope_evidence and scope is not None:
        evidence.append(
            _e(
                "decisions[0].action.scope",
                scope,
                source_type="answer",
                source_locator="WP1_Q_action_scope",
            )
        )
    return {
        "scope_status": scope_status,
        "action_family": action_family,
        "ignored_details": [],
        "companies": [
            {
                "name": company_name,
                "sector": sector,
                "facts": {},
                "constraints": [],
            }
        ],
        "decisions": [
            {
                "action": {
                    "type": "price_change",
                    "pct_increase": 0.2,
                    **({"scope": scope} if scope is not None else {}),
                },
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
        "evidence": evidence,
    }


def _clarification_plan() -> dict[str, object]:
    return {
        "gaps": [
            {
                "category": "action_details",
                "field": "action.scope",
                "verification_check": "formalize_action_payload",
                "reason": "The price-change scope is required to finish the action payload.",
            }
        ],
        "questions": [
            {
                "prompt": "Who exactly would this price change apply to?",
                "rationale": "I need the affected customer scope to complete the price-change action.",
                "targets": ["action.scope"],
                "suggested_options": [
                    {"label": "All customers", "value": "all customers"},
                    {"label": "New customers only", "value": "new customers only"},
                    {"label": "Existing customers only", "value": "existing customers only"},
                ],
                "recommended_option_index": 1,
            }
        ],
    }


def test_stage1_workspace_start_returns_partial_state_and_questions() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient([_parse_output(scope=None), _clarification_plan()])

    result = run_stage1_for_workspace_proposal(
        proposal_id="WP1",
        proposal_text="We want to raise our prices by 20% to increase revenue.",
        workspace_company=workspace_company,
        client=client,
    )

    assert result.outcome == "clarification_needed"
    assert result.partial_battery.decisions[0].action["pct_increase"] == 0.2
    assert result.partial_battery.decisions[0].action.get("scope") is None
    assert result.questions[0].prompt == "Who exactly would this price change apply to?"
    assert result.questions[0].rationale.startswith("I need the affected customer scope")
    assert len(result.questions[0].suggested_options) == 3
    assert result.questions[0].recommended_option_index == 1
    assert result.grounding_report.entries[0].source_type == "workspace"


def test_stage1_workspace_answer_loop_formalizes_from_raw_strings() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient(
        [
            _parse_output(scope=None),
            _clarification_plan(),
            _parse_output(scope="new customers only", include_scope_evidence=True),
            {"gaps": [], "questions": []},
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
        answers={"WP1_Q_action_scope": "new customers only"},
        workspace_company=workspace_company,
        client=client,
    )

    assert result.outcome == "formalized"
    assert result.battery_document.decisions[0].action.scope == "new customers only"
    update_payload = json.loads(client.calls[2]["messages"][1]["content"])
    assert update_payload["answers"] == [
        {
            "question_id": "WP1_Q_action_scope",
            "prompt": "Who exactly would this price change apply to?",
            "answer": "new customers only",
        }
    ]


def test_stage1_skip_returns_completed_with_gaps() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    client = FakeClient([_parse_output(scope=None), _clarification_plan()])

    initial = run_stage1_for_workspace_proposal(
        proposal_id="WP1",
        proposal_text="We want to raise our prices by 20% to increase revenue.",
        workspace_company=workspace_company,
        client=client,
    )
    skipped = skip_stage1_for_workspace_proposal(initial)

    assert skipped.outcome == "completed_with_gaps"
    assert skipped.blocking_fields == ["action.scope"]
    assert skipped.partial_battery.decisions[0].action["pct_increase"] == 0.2
    assert skipped.transcript[-1].kind == "skip"


def test_stage1_batch_run_supports_skip_remaining(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_parse_output(scope=None), _clarification_plan()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(proposal_ids=["P5"], skip_remaining=True),
        client=client,
    )

    assert response.results[0].outcome == "completed_with_gaps"
    assert response.results[0].blocking_fields == ["action.scope"]


def test_stage1_rejects_invalid_parser_json(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient(['{"scope_status": 123}'])

    with pytest.raises(Stage1ExecutionError, match="initial parser JSON"):
        run_stage1(proposal_fixture, Stage1RunRequest(proposal_ids=["P1"]), client=client)


def test_stage1_workspace_payload_excludes_description() -> None:
    workspace_company = WorkspaceCompanyProfile(
        name="Northwind Software",
        sector="B2B SaaS",
        description="Should not be sent to Stage 1 AI.",
    )
    client = FakeClient([_parse_output(scope=None), _clarification_plan()])

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
