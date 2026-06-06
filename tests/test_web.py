from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from decision_prover.settings import ConfigurationError
from decision_prover.web import create_app


def _partial_battery() -> dict:
    return {
        "battery_version": "1.0",
        "title": "Stage 1 Working State - WP1",
        "note_to_candidate": "note",
        "verdict_definitions": {
            "SUPPORTED": "supported",
            "REFUTED": "refuted",
            "UNDECIDABLE": "undecidable",
            "precedence_rule": "hard constraints first",
        },
        "schema": {
            "company": "company",
            "decision": "decision",
            "expected_output_per_decision": "output",
        },
        "companies": [
            {
                "id": "northwind-software",
                "name": "Northwind Software",
                "sector": "B2B SaaS",
                "facts": {},
                "constraints": [],
            }
        ],
        "decisions": [
            {
                "id": "WP1",
                "company": "northwind-software",
                "proposal": "We want to raise our prices by 20%.",
                "action": {"type": "price_change", "pct_increase": 0.2},
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
    }


def _clarification_result(proposal_id: str, proposal_text: str) -> dict:
    return {
        "outcome": "clarification_needed",
        "proposal_id": proposal_id,
        "proposal": proposal_text,
        "scope_status": "supported_family",
        "action_type": "price_change",
        "objective": "Increase revenue through a 20% price increase.",
        "partial_battery": _partial_battery(),
        "grounding_report": {
            "entries": [
                {
                    "field": "companies[0].name",
                    "source_type": "workspace",
                    "source_quote": "Northwind Software",
                    "source_locator": "workspace.name",
                }
            ]
        },
        "blocking_fields": ["action.scope"],
        "gaps": [
            {
                "id": f"{proposal_id}_G_action_scope",
                "category": "action_details",
                "field": "action.scope",
                "verification_check": "formalize_action_payload",
                "reason": "The price-change scope is required to finish the action payload.",
            }
        ],
        "questions": [
            {
                "id": f"{proposal_id}_Q_action_scope",
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
        "ignored_details": [],
        "transcript": [
            {"speaker": "user", "kind": "proposal", "text": proposal_text},
            {
                "speaker": "assistant",
                "kind": "question",
                "text": "Who exactly would this price change apply to?",
                "question_id": f"{proposal_id}_Q_action_scope",
            },
        ],
    }


def _completed_with_gaps_result(proposal_id: str, proposal_text: str) -> dict:
    payload = _clarification_result(proposal_id, proposal_text)
    payload.pop("questions")
    payload["outcome"] = "completed_with_gaps"
    payload["transcript"].append(
        {
            "speaker": "user",
            "kind": "skip",
            "text": "Skip remaining clarification questions and continue with the current state.",
        }
    )
    return payload


def _formalized_result(battery_data: dict, proposal_id: str, proposal_text: str) -> dict:
    battery_document = _partial_battery()
    battery_document["title"] = f"Stage 1 Formalization - {proposal_id}"
    battery_document["decisions"][0]["action"]["scope"] = "new_customers_only"
    return {
        "outcome": "formalized",
        "proposal_id": proposal_id,
        "proposal": proposal_text,
        "battery_document": battery_document,
        "primary_decision_id": proposal_id,
        "grounding_report": {
            "entries": [
                {
                    "field": "decisions[0].action.scope",
                    "source_type": "answer",
                    "source_quote": "new customers only",
                    "source_locator": f"{proposal_id}_Q_action_scope",
                }
            ]
        },
        "ignored_details": [],
        "transcript": [
            {"speaker": "user", "kind": "proposal", "text": proposal_text},
            {
                "speaker": "assistant",
                "kind": "formalization",
                "text": "I have enough information to prepare this proposal for Stage 2 review.",
            },
        ],
    }


def _stage1_response(results: list[dict]) -> dict:
    return {
        "status": {
            "state": "stage1_complete",
            "message": "Stage 1 AI workflow complete.",
        },
        "title": "Natural-Language Proposals - Formalization Set",
        "results": results,
    }


def test_web_health_and_data_endpoints(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.web.app.build_stage1_run_response",
        lambda proposal_fixture, request=None: _stage1_response(
            [_clarification_result("P5", "We want to raise our prices by 20%.")]
        ),
    )

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/stage1").status_code == 200
    assert client.get("/api/stage1").json()["results"][0]["partial_battery"]["decisions"][0]["action"]["pct_increase"] == 0.2
    assert client.get("/api/battery").status_code == 200
    assert client.get("/api/verify/D2").status_code == 200
    assert client.get("/api/proposals").status_code == 200


def test_web_stage1_returns_503_for_missing_openrouter_configuration(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    def _broken_stage1(proposal_fixture, request=None):
        raise ConfigurationError("OPENROUTER_API_KEY is required for Stage 1 AI.")

    monkeypatch.setattr("decision_prover.web.app.build_stage1_run_response", _broken_stage1)

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.get("/api/stage1")
    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is required for Stage 1 AI."


def test_web_workspace_create_answer_skip_and_reset_flow(
    battery_path: Path,
    proposals_path: Path,
    battery_data: dict,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.web.app.build_workspace_stage1_result",
        lambda proposal_id, proposal_text, workspace_company: _clarification_result(
            proposal_id,
            proposal_text,
        ),
    )
    monkeypatch.setattr(
        "decision_prover.web.app.continue_workspace_stage1_result",
        lambda result, answers, workspace_company: _formalized_result(
            battery_data,
            result.proposal_id,
            result.proposal,
        ),
    )
    monkeypatch.setattr(
        "decision_prover.web.app.skip_workspace_stage1_result",
        lambda result: _completed_with_gaps_result(result.proposal_id, result.proposal),
    )

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    create_response = client.put(
        "/api/workspace",
        json={"name": "Northwind Software", "sector": "B2B SaaS", "description": None},
    )
    assert create_response.status_code == 200

    proposal_text = "We want to raise our prices by 20% to increase revenue."
    start_response = client.post("/api/workspace/proposal", json={"proposal": proposal_text})
    assert start_response.status_code == 200
    assert start_response.json()["active_session"]["result"]["outcome"] == "clarification_needed"

    clarification_view = client.get("/")
    assert clarification_view.status_code == 200
    assert "Current Structured State" in clarification_view.text
    assert "Who exactly would this price change apply to?" in clarification_view.text
    assert "Recommended" in clarification_view.text
    assert "Skip and continue" in clarification_view.text

    answer_response = client.post(
        "/api/workspace/proposal/answers",
        json={"answers": {"WP1_Q_action_scope": "new customers only"}},
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["active_session"]["result"]["outcome"] == "formalized"

    reset_response = client.delete("/api/workspace/proposal")
    assert reset_response.status_code == 200
    assert reset_response.json()["active_session"] is None

    client.post("/api/workspace/proposal", json={"proposal": proposal_text})
    skip_response = client.post("/api/workspace/proposal/skip")
    assert skip_response.status_code == 200
    assert skip_response.json()["active_session"]["result"]["outcome"] == "completed_with_gaps"


def test_web_workspace_validation_rejects_blank_required_fields(
    battery_path: Path,
    proposals_path: Path,
) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.put(
        "/api/workspace",
        json={"name": "   ", "sector": "   ", "description": "Optional copy"},
    )
    assert response.status_code == 422
    assert "must not be blank" in response.text
