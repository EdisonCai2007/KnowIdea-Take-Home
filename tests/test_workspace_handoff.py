from __future__ import annotations

import json
from types import SimpleNamespace

from decision_prover.ai.formalization import generate_workspace_formalization
from decision_prover.constants import canonical_battery_metadata
from decision_prover.contracts.output import Stage1CompanyContext, Stage1ReadyOutcome, Stage1WorkingContext
from decision_prover.contracts.workspace import WorkspaceCompanyProfile
from decision_prover.services.operations import build_workspace_stage2_handoff


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
            ],
            what_still_matters=[],
            constraints_mentioned=[],
            success_criteria=["Higher revenue from new customers."],
            notes=[],
        ),
        readiness_summary="Stage 1 is ready because no additional proof-critical clarification questions remain.",
        completion_reason="no_more_questions",
        unresolved_notes=[],
        transcript=[],
    )


def _formalization_payload() -> dict[str, object]:
    return {
        "normalized_bundle": {
            "action": {
                "statement": "Raise prices by 20% for new customers only.",
                "type": "price_change",
                "parameters": {
                    "pct_increase": 0.2,
                    "scope": "new customers only",
                },
            },
            "facts": [],
            "gating_conditions": [],
            "assumptions": [
                {
                    "statement": "Conversion impact is not yet measured for the price change.",
                    "status": "given",
                }
            ],
            "unknowns": [],
            "notes": [],
        },
        "grounding_report": {
            "entries": [
                {
                    "field": "decisions[0].action.scope",
                    "source_type": "answer",
                    "source_quote": "new customers only",
                    "source_locator": "WP1_Q1_1",
                }
            ]
        },
        "notes": [],
    }


def test_generate_workspace_formalization_uses_canonical_metadata_and_answers(
) -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient([_formalization_payload()])

    result = generate_workspace_formalization(
        proposal_id="WP1",
        proposal_text=ready_result.proposal,
        workspace_company=workspace_company,
        ready_result=ready_result,
        answers={"WP1_Q1_1": "new customers only"},
        client=client,
    )

    assert result.status == "formalized"
    assert result.battery_document.model_dump(mode="json", by_alias=True)["note_to_candidate"] == canonical_battery_metadata()["note_to_candidate"]
    payload = json.loads(client.calls[0]["messages"][1]["content"])
    assert payload["workspace_company"]["id"] == "northwind-software"
    assert payload["decision_kernel"]["decision"] == ready_result.working_context.decision
    assert payload["answers"] == [{"question_id": "WP1_Q1_1", "answer": "new customers only"}]
    assert result.battery_document.decisions[0].id == "WP1"
    assert result.battery_document.decisions[0].proposal == ready_result.proposal


def test_build_workspace_stage2_handoff_returns_formalization_error_for_invalid_json(
) -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient(['{"normalized_bundle": 123}'])

    formalization, verification = build_workspace_stage2_handoff(
        ready_result,
        workspace_company=workspace_company,
        answers={"WP1_Q1_1": "new customers only"},
        client=client,
    )

    assert formalization is not None
    assert formalization.status == "formalization_error"
    assert verification is None


def test_generate_workspace_formalization_uses_generic_fallback_action_when_missing() -> None:
    workspace_company = WorkspaceCompanyProfile(name="Northwind Software", sector="B2B SaaS")
    ready_result = _ready_result()
    client = FakeClient(
        [
            {
                "normalized_bundle": {
                    "action": {
                        "statement": ready_result.working_context.decision,
                        "type": "generic_weekend_shift",
                        "parameters": {},
                    },
                    "facts": [],
                    "gating_conditions": [],
                    "assumptions": [],
                    "unknowns": [],
                    "notes": [],
                },
                "grounding_report": {"entries": []},
                "notes": [],
            }
        ]
    )

    result = generate_workspace_formalization(
        proposal_id="WP1",
        proposal_text=ready_result.proposal,
        workspace_company=workspace_company,
        ready_result=ready_result,
        answers={},
        client=client,
    )

    action = result.battery_document.decisions[0].action.model_dump(mode="json")
    assert action["type"] == "generic_decision"
    assert action["summary"] == ready_result.working_context.decision
    assert any("generic fallback action" in note for note in result.notes)
