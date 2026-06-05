from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from decision_prover.web import create_app
from decision_prover.settings import ConfigurationError


def _battery_document(battery_data: dict, proposal_id: str, *, scope: str = "new_customers") -> dict:
    return {
        "battery_version": battery_data["battery_version"],
        "title": f"Stage 1 Formalization - {proposal_id}",
        "note_to_candidate": battery_data["note_to_candidate"],
        "verdict_definitions": battery_data["verdict_definitions"],
        "schema": battery_data["schema"],
        "companies": [
            {
                "id": "northwind_software",
                "name": "Northwind Software",
                "sector": "B2B SaaS",
                "facts": {},
                "constraints": [],
            }
        ],
        "decisions": [
            {
                "id": proposal_id,
                "company": "northwind_software",
                "proposal": "We want to raise our prices by 20%.",
                "action": {
                    "type": "price_change",
                    "pct_increase": 0.2,
                    "scope": scope,
                },
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
    }


def _clarification_result(proposal_id: str) -> dict:
    return {
        "outcome": "clarification_needed",
        "proposal_id": proposal_id,
        "proposal": "Placeholder proposal text.",
        "scope_status": "supported_family",
        "action_type": "one_time_spend",
        "objective": "Preserve runway while evaluating the spend.",
        "blocking_fields": ["company.name", "company.sector"],
        "gaps": [
            {
                "id": f"{proposal_id}_G_company_name",
                "category": "company_metadata",
                "field": "company.name",
                "verification_check": "identify_company",
                "reason": "The company name is required for final formalization.",
            }
        ],
        "questions": [
            {
                "id": f"{proposal_id}_Q_company_name",
                "field": "company.name",
                "question": "What is the company name?",
                "verification_check": "identify_company",
                "rationale": "The battery document requires an explicit company name.",
            }
        ],
        "ignored_details": [],
        "transcript": [
            {"speaker": "user", "kind": "proposal", "text": "Placeholder proposal text."}
        ],
    }


def _formalized_result(battery_data: dict, proposal_id: str) -> dict:
    return {
        "outcome": "formalized",
        "proposal_id": proposal_id,
        "proposal": "We want to raise our prices by 20%.",
        "battery_document": _battery_document(battery_data, proposal_id),
        "primary_decision_id": proposal_id,
        "grounding_report": {
            "entries": [
                {
                    "field": "companies[0].name",
                    "source_type": "answer",
                    "source_quote": "Northwind Software",
                    "source_locator": f"{proposal_id}_Q_company_name",
                }
            ]
        },
        "ignored_details": [],
        "transcript": [
            {
                "speaker": "assistant",
                "kind": "formalization",
                "text": f"Formalized {proposal_id} into a battery-shaped document.",
            }
        ],
    }


def _stage1_response(results: list[dict]) -> dict:
    return {
        "status": {
            "state": "stage1_complete",
            "message": "Stage 1 AI planning complete.",
        },
        "title": "Natural-Language Proposals - Formalization Set",
        "results": results,
    }


def test_web_health_and_data_endpoints(
    battery_path: Path,
    proposals_path: Path,
    battery_data: dict,
    monkeypatch,
) -> None:
    def _fake_stage1(proposal_fixture, request=None):
        if request and request.answers:
            return _stage1_response([_formalized_result(battery_data, "P5")])
        return _stage1_response([_clarification_result("P3")])

    monkeypatch.setattr("decision_prover.web.app.build_stage1_run_response", _fake_stage1)

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    battery = client.get("/api/battery")
    assert battery.status_code == 200
    assert len(battery.json()["companies"]) == 3
    assert len(battery.json()["decisions"]) == 12

    contexts = client.get("/api/battery/contexts")
    assert contexts.status_code == 200
    assert len(contexts.json()) == 12

    supported_verification = client.get("/api/verify/D2")
    assert supported_verification.status_code == 200
    assert supported_verification.json()["classification"] == "SUPPORTED"

    undecidable_verification = client.get("/api/verify/D1")
    assert undecidable_verification.status_code == 200
    assert undecidable_verification.json()["classification"] == "UNDECIDABLE"
    assert undecidable_verification.json()["pivotal_assumption"]
    assert undecidable_verification.json()["supported_if"]
    assert undecidable_verification.json()["refuted_if"]

    proposals = client.get("/api/proposals")
    assert proposals.status_code == 200
    assert len(proposals.json()["proposals"]) == 6

    workspace = client.get("/api/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["active_company"] is None

    stage1 = client.get("/api/stage1")
    assert stage1.status_code == 200
    assert stage1.json()["status"]["state"] == "stage1_complete"
    assert stage1.json()["results"][0]["proposal_id"] == "P3"
    assert stage1.json()["results"][0]["outcome"] == "clarification_needed"
    assert stage1.json()["results"][0]["blocking_fields"] == ["company.name", "company.sector"]

    answered_stage1 = client.post(
        "/api/stage1",
        json={
            "proposal_ids": ["P5"],
            "answers": {
                "P5": {
                    "P5_Q_company_name": "Northwind Software",
                    "P5_Q_company_sector": "B2B SaaS",
                    "P5_Q_action_scope": "new customers only",
                }
            },
        },
    )
    assert answered_stage1.status_code == 200
    assert answered_stage1.json()["results"][0]["outcome"] == "formalized"
    assert answered_stage1.json()["results"][0]["primary_decision_id"] == "P5"
    assert answered_stage1.json()["results"][0]["battery_document"]["decisions"][0]["action"]["scope"] == "new_customers"


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


def test_web_index_renders_phase5_landing(battery_path: Path, proposals_path: Path) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Decision Prover" in response.text
    assert "Current Phases Roadmap" in response.text
    assert "Create Active Workspace" in response.text
    assert "Create company workspace" in response.text
    assert "Set up the company context before proposal intake." in response.text
    assert "Stage 1 Interview &amp; Formalize" not in response.text
    assert "Raw Proposals" not in response.text
    assert "Normalized Contexts" not in response.text
    assert "loadStage1()" not in response.text


def test_web_workspace_create_and_edit_flow(battery_path: Path, proposals_path: Path) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    create_response = client.put(
        "/api/workspace",
        json={
            "name": "  Northwind Software  ",
            "sector": "  B2B SaaS ",
            "description": "   ",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json() == {
        "active_company": {
            "name": "Northwind Software",
            "sector": "B2B SaaS",
            "description": None,
        }
    }

    workspace = client.get("/api/workspace")
    assert workspace.status_code == 200
    assert workspace.json() == create_response.json()

    landing = client.get("/")
    assert landing.status_code == 200
    assert "Active Company Workspace" in landing.text
    assert "Northwind Software" in landing.text
    assert "Proposal composer for Northwind Software" in landing.text
    assert "Analyze Proposal (Phase 6)" in landing.text
    assert "Edit company" in landing.text
    assert "Raw Proposals" not in landing.text
    assert "Stage 1 Interview &amp; Formalize" not in landing.text

    edit_response = client.put(
        "/api/workspace",
        json={
            "name": "Northwind Labs",
            "sector": "Vertical SaaS",
            "description": "Financial workflow automation for operators.",
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json() == {
        "active_company": {
            "name": "Northwind Labs",
            "sector": "Vertical SaaS",
            "description": "Financial workflow automation for operators.",
        }
    }

    edited_landing = client.get("/")
    assert edited_landing.status_code == 200
    assert "Northwind Labs" in edited_landing.text
    assert "Vertical SaaS" in edited_landing.text
    assert "Financial workflow automation for operators." in edited_landing.text


def test_web_workspace_validation_rejects_blank_required_fields(
    battery_path: Path,
    proposals_path: Path,
) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.put(
        "/api/workspace",
        json={
            "name": "   ",
            "sector": "   ",
            "description": "Optional copy",
        },
    )
    assert response.status_code == 422
    assert "must not be blank" in response.text

    workspace = client.get("/api/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["active_company"] is None
