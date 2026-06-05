import json
from pathlib import Path

from typer.testing import CliRunner

from decision_prover.cli import app

runner = CliRunner()


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


def test_proposals_run_cli_returns_stage1_pending(proposals_path: Path) -> None:
    result = runner.invoke(app, ["proposals", "run", "--input", str(proposals_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"]["state"] == "stage1_pending"
    assert len(payload["proposals"]) == 6


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
