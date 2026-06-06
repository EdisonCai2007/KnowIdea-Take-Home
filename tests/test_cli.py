import json
from pathlib import Path

from typer.testing import CliRunner

from decision_prover.cli import app

runner = CliRunner()


def _partial_battery() -> dict:
    return {
        "battery_version": "1.0",
        "title": "Stage 1 Working State - P5",
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
                "id": "P5",
                "company": "northwind-software",
                "proposal": "We want to raise our prices by 20%.",
                "action": {"type": "price_change", "pct_increase": 0.2},
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
    }


def _clarification_result(proposal_id: str) -> dict:
    return {
        "outcome": "clarification_needed",
        "proposal_id": proposal_id,
        "proposal": "We want to raise our prices by 20%.",
        "scope_status": "supported_family",
        "action_type": "price_change",
        "objective": "Increase revenue through a 20% price increase.",
        "partial_battery": _partial_battery(),
        "grounding_report": {"entries": []},
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
        "transcript": [{"speaker": "user", "kind": "proposal", "text": "We want to raise our prices by 20%."}],
    }


def _completed_with_gaps_result(proposal_id: str) -> dict:
    payload = _clarification_result(proposal_id)
    payload["outcome"] = "completed_with_gaps"
    payload.pop("questions")
    return payload


def _formalized_result(proposal_id: str) -> dict:
    battery_document = _partial_battery()
    battery_document["title"] = f"Stage 1 Formalization - {proposal_id}"
    battery_document["decisions"][0]["action"]["scope"] = "new_customers_only"
    return {
        "outcome": "formalized",
        "proposal_id": proposal_id,
        "proposal": "We want to raise our prices by 20%.",
        "battery_document": battery_document,
        "primary_decision_id": proposal_id,
        "grounding_report": {"entries": []},
        "ignored_details": [],
        "transcript": [{"speaker": "assistant", "kind": "formalization", "text": "ready"}],
    }


def _stage1_response(results: list[dict]) -> dict:
    return {
        "status": {"state": "stage1_complete", "message": "Stage 1 AI workflow complete."},
        "title": "Natural-Language Proposals - Formalization Set",
        "results": results,
    }


def test_fixtures_validate_cli(battery_path: Path) -> None:
    result = runner.invoke(app, ["fixtures", "validate", "--input", str(battery_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["companies"] == 3


def test_proposals_run_cli_returns_new_stage1_results(
    proposals_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.cli.build_stage1_run_response",
        lambda proposal_fixture, request: _stage1_response(
            [_clarification_result("P3"), _formalized_result("P5")]
        ),
    )

    result = runner.invoke(app, ["proposals", "run", "--input", str(proposals_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["outcome"] for item in payload["results"]] == ["clarification_needed", "formalized"]
    assert payload["results"][0]["partial_battery"]["decisions"][0]["action"]["pct_increase"] == 0.2


def test_proposals_run_cli_supports_skip_remaining_flag(
    proposals_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_stage1(proposal_fixture, request):
        captured["skip_remaining"] = request.skip_remaining
        return _stage1_response([_completed_with_gaps_result("P5")])

    monkeypatch.setattr("decision_prover.cli.build_stage1_run_response", _fake_stage1)

    result = runner.invoke(
        app,
        ["proposals", "run", "--input", str(proposals_path), "--proposal-id", "P5", "--skip-remaining"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["outcome"] == "completed_with_gaps"
    assert captured["skip_remaining"] is True
