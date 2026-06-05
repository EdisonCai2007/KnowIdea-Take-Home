import json
from pathlib import Path

from typer.testing import CliRunner

from decision_prover.cli import app
from decision_prover.settings import ConfigurationError

runner = CliRunner()


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
            },
            {
                "id": f"{proposal_id}_G_company_sector",
                "category": "company_metadata",
                "field": "company.sector",
                "verification_check": "identify_sector",
                "reason": "The company sector is required for final formalization.",
            },
        ],
        "questions": [
            {
                "id": f"{proposal_id}_Q_company_name",
                "field": "company.name",
                "question": "What is the company name?",
                "verification_check": "identify_company",
                "rationale": "The battery document requires an explicit company name.",
            },
            {
                "id": f"{proposal_id}_Q_company_sector",
                "field": "company.sector",
                "question": "What sector is the company in?",
                "verification_check": "identify_sector",
                "rationale": "The battery document requires an explicit company sector.",
            },
        ],
        "ignored_details": [],
        "transcript": [
            {"speaker": "user", "kind": "proposal", "text": "Placeholder proposal text."},
            {
                "speaker": "assistant",
                "kind": "question",
                "text": "What is the company name?",
                "question_id": f"{proposal_id}_Q_company_name",
            },
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
                },
                {
                    "field": "decisions[0].action.scope",
                    "source_type": "answer",
                    "source_quote": "new customers only",
                    "source_locator": f"{proposal_id}_Q_action_scope",
                },
            ]
        },
        "ignored_details": [],
        "transcript": [
            {"speaker": "user", "kind": "proposal", "text": "We want to raise our prices by 20%."},
            {
                "speaker": "assistant",
                "kind": "formalization",
                "text": f"Formalized {proposal_id} into a battery-shaped document.",
            },
        ],
    }


def _stage1_response(battery_data: dict, results: list[dict]) -> dict:
    return {
        "status": {
            "state": "stage1_complete",
            "message": "Stage 1 AI planning complete.",
        },
        "title": "Natural-Language Proposals - Formalization Set",
        "results": results,
    }


def test_fixtures_validate_cli(battery_path: Path) -> None:
    result = runner.invoke(app, ["fixtures", "validate", "--input", str(battery_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "ok",
        "companies": 3,
        "decisions": 12,
        "decision_contexts": 12,
    }


def test_fixtures_export_cli_returns_all_contexts(battery_path: Path) -> None:
    result = runner.invoke(app, ["fixtures", "export", "--input", str(battery_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 12
    assert payload[0]["company"]["id"] == "lumen"


def test_fixtures_export_cli_returns_single_context(battery_path: Path) -> None:
    result = runner.invoke(
        app,
        ["fixtures", "export", "--input", str(battery_path), "--decision-id", "D5"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "D5"
    assert payload["company"]["id"] == "harvest"


def test_proposals_run_cli_returns_stage1_results(
    proposals_path: Path,
    battery_data: dict,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.cli.build_stage1_run_response",
        lambda proposal_fixture, request: _stage1_response(
            battery_data,
            [_clarification_result("P3"), _formalized_result(battery_data, "P5")],
        ),
    )

    result = runner.invoke(app, ["proposals", "run", "--input", str(proposals_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"]["state"] == "stage1_complete"
    assert [item["outcome"] for item in payload["results"]] == [
        "clarification_needed",
        "formalized",
    ]
    assert payload["results"][1]["battery_document"]["decisions"][0]["action"]["scope"] == "new_customers"
    assert payload["results"][1]["grounding_report"]["entries"][0]["source_type"] == "answer"


def test_proposals_run_cli_supports_proposal_filter(
    proposals_path: Path,
    battery_data: dict,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_stage1(proposal_fixture, request):
        captured["proposal_ids"] = request.proposal_ids
        return _stage1_response(battery_data, [_clarification_result("P5")])

    monkeypatch.setattr("decision_prover.cli.build_stage1_run_response", _fake_stage1)

    result = runner.invoke(
        app,
        ["proposals", "run", "--input", str(proposals_path), "--proposal-id", "P5"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert captured["proposal_ids"] == ["P5"]
    assert [item["proposal_id"] for item in payload["results"]] == ["P5"]
    assert payload["results"][0]["outcome"] == "clarification_needed"
    assert payload["results"][0]["scope_status"] == "supported_family"


def test_proposals_run_cli_supports_answers_file(
    proposals_path: Path,
    battery_data: dict,
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_stage1(proposal_fixture, request):
        captured["answers"] = request.answers
        return _stage1_response(battery_data, [_formalized_result(battery_data, "P5")])

    monkeypatch.setattr("decision_prover.cli.build_stage1_run_response", _fake_stage1)

    answers_path = tmp_path / "stage1_answers.json"
    answers_path.write_text(
        json.dumps(
            {
                "P5": {
                    "P5_Q_company_name": "Northwind Software",
                    "P5_Q_company_sector": "B2B SaaS",
                    "P5_Q_action_scope": "new customers only",
                }
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "proposals",
            "run",
            "--input",
            str(proposals_path),
            "--proposal-id",
            "P5",
            "--answers",
            str(answers_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert captured["answers"] == {
        "P5": {
            "P5_Q_company_name": "Northwind Software",
            "P5_Q_company_sector": "B2B SaaS",
            "P5_Q_action_scope": "new customers only",
        }
    }
    assert payload["results"][0]["outcome"] == "formalized"
    assert payload["results"][0]["battery_document"]["decisions"][0]["action"]["scope"] == "new_customers"


def test_proposals_run_cli_surfaces_configuration_error(
    proposals_path: Path,
    monkeypatch,
) -> None:
    def _broken_stage1(proposal_fixture, request):
        raise ConfigurationError("OPENROUTER_API_KEY is required for Stage 1 AI.")

    monkeypatch.setattr(
        "decision_prover.cli.build_stage1_run_response",
        _broken_stage1,
    )

    result = runner.invoke(app, ["proposals", "run", "--input", str(proposals_path)])

    assert result.exit_code == 1
    assert "OPENROUTER_API_KEY" in result.stderr


def test_verify_run_cli_returns_undecidable_payload(battery_path: Path) -> None:
    result = runner.invoke(
        app,
        ["verify", "run", "--input", str(battery_path), "--decision-id", "D1"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["classification"] == "UNDECIDABLE"
    assert payload["derivation"][-1]["rule"] == "check_hire_objective"
    assert payload["pivotal_assumption"]
    assert payload["supported_if"]
    assert payload["refuted_if"]
