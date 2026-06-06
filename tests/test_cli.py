import json
from pathlib import Path

from typer.testing import CliRunner

from decision_prover.cli import app

runner = CliRunner()


def _stage1_response(results: list[dict]) -> dict:
    return {
        "status": {"state": "stage1_complete", "message": "Stage 1 AI workflow complete."},
        "title": "Natural-Language Proposals",
        "results": results,
    }


def _clarification_result(proposal_id: str) -> dict:
    return {
        "outcome": "clarification_needed",
        "proposal_id": proposal_id,
        "proposal": "We want to raise our prices by 20%.",
        "working_context": {
            "company": {"name": "Northwind Software", "sector": "B2B SaaS"},
            "proposal": "We want to raise our prices by 20%.",
            "decision": "Raise prices by 20% for new customers only.",
            "objective": "Increase revenue while monitoring conversion quality.",
            "what_we_know": ["The proposal mentions a 20% price increase."],
            "what_still_matters": ["Which customers are affected."],
            "constraints_mentioned": [],
            "success_criteria": ["Higher revenue from new customers."],
            "notes": [],
        },
        "questions": [
            {
                "id": f"{proposal_id}_Q1_1",
                "prompt": "Who exactly would this price change apply to?",
                "rationale": "I need the affected customer scope to tighten the decision brief.",
                "suggested_answers": [
                    {"label": "All customers", "value": "all customers"},
                    {"label": "New customers only", "value": "new customers only"},
                    {"label": "Existing customers only", "value": "existing customers only"},
                ],
                "recommended_answer_index": 1,
                "allow_custom_answer": True,
            }
        ],
        "transcript": [],
    }


def _ready_result(proposal_id: str) -> dict:
    return {
        "outcome": "stage1_ready",
        "proposal_id": proposal_id,
        "proposal": "We want to raise our prices by 20%.",
        "working_context": {
            "company": {"name": "Northwind Software", "sector": "B2B SaaS"},
            "proposal": "We want to raise our prices by 20%.",
            "decision": "Raise prices by 20% for new customers only.",
            "objective": "Increase revenue while monitoring conversion quality.",
            "what_we_know": [
                "The proposal mentions a 20% price increase.",
                "The price change applies to new customers only.",
            ],
            "what_still_matters": [],
            "constraints_mentioned": [],
            "success_criteria": ["Higher revenue from new customers."],
            "notes": [],
        },
        "readiness_summary": "Stage 1 is ready because no additional proof-critical clarification questions remain.",
        "completion_reason": "no_more_questions",
        "unresolved_notes": [],
        "transcript": [],
    }


def test_fixtures_validate_cli(battery_path: Path) -> None:
    result = runner.invoke(app, ["fixtures", "validate", "--input", str(battery_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["companies"] == 3


def test_proposals_run_cli_returns_current_stage1_results(
    proposals_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.cli.build_stage1_run_response",
        lambda proposal_fixture, request: _stage1_response(
            [_clarification_result("P3"), _ready_result("P5")]
        ),
    )

    result = runner.invoke(app, ["proposals", "run", "--input", str(proposals_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["outcome"] for item in payload["results"]] == ["clarification_needed", "stage1_ready"]
    assert payload["results"][0]["questions"][0]["recommended_answer_index"] == 1


def test_proposals_run_cli_supports_skip_remaining_flag(
    proposals_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_stage1(proposal_fixture, request):
        captured["skip_remaining"] = request.skip_remaining
        return _stage1_response([_ready_result("P5")])

    monkeypatch.setattr("decision_prover.cli.build_stage1_run_response", _fake_stage1)

    result = runner.invoke(
        app,
        ["proposals", "run", "--input", str(proposals_path), "--proposal-id", "P5", "--skip-remaining"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["outcome"] == "stage1_ready"
    assert captured["skip_remaining"] is True
