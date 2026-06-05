from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel
from pydantic import ValidationError

from .constants import DEFAULT_BATTERY_PATH, DEFAULT_PROPOSALS_PATH
from .contracts.output import Stage1RunRequest, ValidationSummary
from .fixtures import FixtureLoadError, get_decision_context, load_battery_fixture, load_proposals_fixture
from .settings import ConfigurationError
from .services import build_stage1_run_response
from .stage1 import Stage1ExecutionError, Stage1InputError
from .verifier import explain_verification, verify_decision

app = typer.Typer(help="Decision Prover Phase 1 tooling.", no_args_is_help=True)
fixtures_app = typer.Typer(help="Validate and export fixture data.", no_args_is_help=True)
proposals_app = typer.Typer(help="Parse raw proposal inputs.", no_args_is_help=True)
verify_app = typer.Typer(help="Load normalized decision contexts for verification.", no_args_is_help=True)
ui_app = typer.Typer(help="Serve the minimal audit UI.", no_args_is_help=True)

app.add_typer(fixtures_app, name="fixtures")
app.add_typer(proposals_app, name="proposals")
app.add_typer(verify_app, name="verify")
app.add_typer(ui_app, name="ui")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _emit_json(value: Any) -> None:
    typer.echo(json.dumps(_to_jsonable(value), indent=2))


def _exit_with_fixture_error(error: FixtureLoadError) -> None:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=1)


def _exit_with_configuration_error(error: ConfigurationError) -> None:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=1)


def _exit_with_stage1_input_error(error: Stage1InputError | ValidationError) -> None:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=1)


def _load_stage1_request(
    proposal_ids: list[str],
    answers_path: Path | None,
) -> Stage1RunRequest:
    answers_payload: dict[str, Any] = {}
    if answers_path is not None:
        raw = json.loads(answers_path.read_text())
        if isinstance(raw, dict) and "answers" in raw:
            answers_payload = raw["answers"]
        else:
            answers_payload = raw
    return Stage1RunRequest(
        proposal_ids=proposal_ids,
        answers=answers_payload,
    )


@fixtures_app.command("validate")
def validate_fixture(input: Path = typer.Option(..., exists=True, readable=True, dir_okay=False)) -> None:
    """Validate the battery fixture and print a concise JSON summary."""
    try:
        loaded_battery = load_battery_fixture(input)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)

    summary = ValidationSummary(
        status="ok",
        companies=len(loaded_battery.fixture.companies),
        decisions=len(loaded_battery.fixture.decisions),
        decision_contexts=len(loaded_battery.decision_contexts),
    )
    _emit_json(summary)


@fixtures_app.command("export")
def export_fixture(
    input: Path = typer.Option(..., exists=True, readable=True, dir_okay=False),
    decision_id: str | None = typer.Option(None, help="Return one normalized decision context by id."),
) -> None:
    """Export normalized decision contexts."""
    try:
        loaded_battery = load_battery_fixture(input)
        if decision_id:
            _emit_json(get_decision_context(loaded_battery, decision_id))
        else:
            _emit_json(loaded_battery.decision_contexts)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)


@proposals_app.command("run")
def run_proposals(
    input: Path = typer.Option(..., exists=True, readable=True, dir_okay=False),
    proposal_id: list[str] = typer.Option(
        None,
        "--proposal-id",
        help="Limit Stage 1 execution to one or more proposal ids.",
    ),
    answers: Path | None = typer.Option(
        None,
        exists=True,
        readable=True,
        dir_okay=False,
        help="Optional JSON file mapping proposal ids to question answers.",
    ),
) -> None:
    """Run Stage 1 planning and formalization on raw proposal markdown."""
    try:
        proposal_fixture = load_proposals_fixture(input)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)

    try:
        stage1_request = _load_stage1_request(proposal_id or [], answers)
        _emit_json(build_stage1_run_response(proposal_fixture, stage1_request))
    except ConfigurationError as error:
        _exit_with_configuration_error(error)
    except Stage1ExecutionError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)
    except (Stage1InputError, ValidationError, json.JSONDecodeError) as error:
        _exit_with_stage1_input_error(error)


@verify_app.command("run")
def run_verifier(
    input: Path = typer.Option(..., exists=True, readable=True, dir_okay=False),
    decision_id: str = typer.Option(..., help="Decision id to normalize and return."),
) -> None:
    """Run the Phase 2 verifier on one normalized decision context."""
    try:
        loaded_battery = load_battery_fixture(input)
        decision_context = get_decision_context(loaded_battery, decision_id)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)

    _emit_json(verify_decision(decision_context))


@verify_app.command("explain")
def explain_verifier(
    input: Path = typer.Option(..., exists=True, readable=True, dir_okay=False),
    decision_id: str = typer.Option(..., help="Decision id to normalize and explain."),
) -> None:
    """Run the verifier and request an independent AI verdict alongside the checked result."""
    try:
        loaded_battery = load_battery_fixture(input)
        decision_context = get_decision_context(loaded_battery, decision_id)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)

    try:
        _emit_json(explain_verification(decision_context))
    except ConfigurationError as error:
        _exit_with_configuration_error(error)


@ui_app.command("serve")
def serve_ui(
    battery_input: Path = typer.Option(
        DEFAULT_BATTERY_PATH,
        exists=True,
        readable=True,
        dir_okay=False,
        help="Battery fixture JSON path.",
    ),
    proposal_input: Path = typer.Option(
        DEFAULT_PROPOSALS_PATH,
        exists=True,
        readable=True,
        dir_okay=False,
        help="Proposal markdown path.",
    ),
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, min=1, max=65535, help="Bind port."),
) -> None:
    """Serve the minimal audit UI."""
    from .web import create_app

    try:
        app_instance = create_app(battery_input=battery_input, proposal_input=proposal_input)
    except FixtureLoadError as error:
        _exit_with_fixture_error(error)

    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        typer.echo("uvicorn is not installed. Install project dependencies first.", err=True)
        raise typer.Exit(code=1) from exc

    uvicorn.run(app_instance, host=host, port=port)
