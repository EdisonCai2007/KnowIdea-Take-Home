from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..constants import DEFAULT_BATTERY_PATH, DEFAULT_PROPOSALS_PATH
from ..contracts.battery import DecisionBattery
from ..contracts.context import DecisionContextList
from ..contracts.output import (
    Stage1RunRequest,
    Stage1RunResponse,
    VerificationExplainResponse,
    VerificationResult,
)
from ..contracts.workspace import WorkspaceCompanyProfile, WorkspaceState
from ..fixtures import FixtureLoadError, LoadedBattery, get_decision_context, load_battery_fixture, load_proposals_fixture
from ..proposals import ProposalFixture
from ..settings import ConfigurationError
from ..stage1 import Stage1ExecutionError, Stage1InputError
from ..services import build_stage1_run_response
from ..verifier import explain_verification, verify_decision

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def create_app(
    battery_input: str | Path = DEFAULT_BATTERY_PATH,
    proposal_input: str | Path = DEFAULT_PROPOSALS_PATH,
) -> FastAPI:
    loaded_battery: LoadedBattery = load_battery_fixture(battery_input)
    proposal_fixture: ProposalFixture = load_proposals_fixture(proposal_input)

    app = FastAPI(title="Decision Prover", version=__version__)
    app.state.loaded_battery = loaded_battery
    app.state.proposal_fixture = proposal_fixture
    app.state.battery_input = str(Path(battery_input).resolve())
    app.state.proposal_input = str(Path(proposal_input).resolve())
    app.state.workspace = WorkspaceState()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/battery", response_model=DecisionBattery)
    def get_battery() -> DecisionBattery:
        return app.state.loaded_battery.fixture

    @app.get("/api/battery/contexts", response_model=DecisionContextList)
    def get_battery_contexts() -> DecisionContextList:
        return DecisionContextList(root=app.state.loaded_battery.decision_contexts)

    @app.get("/api/verify/{decision_id}", response_model=VerificationResult)
    def get_verification(decision_id: str) -> VerificationResult:
        try:
            decision_context = get_decision_context(app.state.loaded_battery, decision_id)
        except FixtureLoadError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return verify_decision(decision_context)

    @app.get("/api/verify/{decision_id}/explain", response_model=VerificationExplainResponse)
    def get_verification_explanation(decision_id: str) -> VerificationExplainResponse:
        try:
            decision_context = get_decision_context(app.state.loaded_battery, decision_id)
        except FixtureLoadError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            return explain_verification(decision_context)
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/proposals", response_model=ProposalFixture)
    def get_proposals() -> ProposalFixture:
        return app.state.proposal_fixture

    @app.get("/api/workspace", response_model=WorkspaceState)
    def get_workspace() -> WorkspaceState:
        return app.state.workspace

    @app.put("/api/workspace", response_model=WorkspaceState)
    def put_workspace(payload: WorkspaceCompanyProfile) -> WorkspaceState:
        app.state.workspace = WorkspaceState(active_company=payload)
        return app.state.workspace

    @app.get("/api/stage1", response_model=Stage1RunResponse)
    def get_stage1() -> Stage1RunResponse:
        try:
            return build_stage1_run_response(app.state.proposal_fixture)
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1ExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/stage1", response_model=Stage1RunResponse)
    def run_stage1(request_body: Stage1RunRequest) -> Stage1RunResponse:
        try:
            return build_stage1_run_response(app.state.proposal_fixture, request_body)
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1ExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1InputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "workspace": app.state.workspace,
            },
        )

    return app
