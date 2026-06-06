from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..constants import DEFAULT_BATTERY_PATH, DEFAULT_PROPOSALS_PATH
from ..contracts.battery import DecisionBattery
from ..contracts.context import DecisionContextList
from ..contracts.output import (
    Stage1Outcome,
    Stage1RunRequest,
    Stage1RunResponse,
    Stage2FormalizationOutcome,
    VerificationExplainResponse,
    VerificationResult,
)
from ..contracts.workspace import (
    WorkspaceCompanyProfile,
    WorkspaceProposalAnswersRequest,
    WorkspaceProposalSession,
    WorkspaceProposalSessionState,
    WorkspaceProposalSubmitRequest,
    WorkspaceState,
)
from ..fixtures import FixtureLoadError, LoadedBattery, get_decision_context, load_battery_fixture, load_proposals_fixture
from ..proposals import ProposalFixture
from ..runtime_logging import log_event
from ..settings import ConfigurationError, get_openrouter_settings
from ..stage1 import Stage1ExecutionError, Stage1InputError
from ..services import build_stage1_run_response, build_workspace_stage1_result
from ..services import build_workspace_stage2_handoff, continue_workspace_stage1_result
from ..services import skip_workspace_stage1_result
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
    app.state.proposal_session = WorkspaceProposalSessionState()
    app.state.proposal_counter = 0

    def _next_workspace_proposal_id() -> str:
        app.state.proposal_counter += 1
        return f"WP{app.state.proposal_counter}"

    def _normalized_answer_map(answers: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in answers.items():
            cleaned = value.strip()
            if cleaned:
                normalized[key] = cleaned
        return normalized

    def _workspace_session_with_handoff(
        *,
        proposal_id: str,
        workspace_company: WorkspaceCompanyProfile,
        proposal: str,
        answers: dict[str, str],
        result: Stage1Outcome,
    ) -> WorkspaceProposalSession:
        formalization: Stage2FormalizationOutcome | None = None
        verification_result: VerificationResult | None = None
        if result.outcome == "stage1_ready":
            formalization, verification_result = build_workspace_stage2_handoff(
                result,
                workspace_company=workspace_company,
                answers=answers,
            )
        return WorkspaceProposalSession(
            proposal_id=proposal_id,
            workspace_company=workspace_company,
            proposal=proposal,
            answers=answers,
            result=result,
            formalization=formalization,
            verification_result=verification_result,
        )

    def _log_app_event(
        event: str,
        *,
        payload: dict[str, object],
        console_message: str,
    ) -> None:
        try:
            settings = get_openrouter_settings(require_api_key=False)
        except ConfigurationError:
            return
        log_event(
            settings=settings,
            event=event,
            payload=payload,
            console_message=console_message,
        )

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
        if app.state.proposal_session.active_session is not None:
            raise HTTPException(
                status_code=409,
                detail="Reset the active proposal interview before editing the company workspace.",
            )
        app.state.workspace = WorkspaceState(active_company=payload)
        return app.state.workspace

    @app.get("/api/workspace/proposal", response_model=WorkspaceProposalSessionState)
    def get_workspace_proposal() -> WorkspaceProposalSessionState:
        return app.state.proposal_session

    @app.post("/api/workspace/proposal", response_model=WorkspaceProposalSessionState)
    def start_workspace_proposal(
        request_body: WorkspaceProposalSubmitRequest,
    ) -> WorkspaceProposalSessionState:
        workspace_company = app.state.workspace.active_company
        if workspace_company is None:
            raise HTTPException(
                status_code=409,
                detail="Create a company workspace before starting proposal intake.",
            )
        if app.state.proposal_session.active_session is not None:
            raise HTTPException(
                status_code=409,
                detail="Reset the active proposal interview before starting a new proposal.",
            )

        proposal_id = _next_workspace_proposal_id()
        _log_app_event(
            "stage1.start",
            payload={
                "proposal_id": proposal_id,
                "source": "workspace_http",
                "submitted_answer_count": 0,
            },
            console_message=f"stage1.start proposal_id={proposal_id} source=workspace_http",
        )
        try:
            result = build_workspace_stage1_result(
                proposal_id=proposal_id,
                proposal_text=request_body.proposal,
                workspace_company=workspace_company,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1ExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1InputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        app.state.proposal_session = WorkspaceProposalSessionState(
            active_session=_workspace_session_with_handoff(
                proposal_id=proposal_id,
                workspace_company=workspace_company,
                proposal=request_body.proposal,
                answers={},
                result=result,
            )
        )
        return app.state.proposal_session

    @app.post("/api/workspace/proposal/answers", response_model=WorkspaceProposalSessionState)
    def answer_workspace_proposal(
        request_body: WorkspaceProposalAnswersRequest,
    ) -> WorkspaceProposalSessionState:
        active_session = app.state.proposal_session.active_session
        if active_session is None:
            raise HTTPException(
                status_code=409,
                detail="Start a proposal interview before submitting clarification answers.",
            )
        if active_session.result.outcome != "clarification_needed":
            raise HTTPException(
                status_code=409,
                detail="The active proposal is already Stage 1 ready. Reset the interview to start again.",
            )

        merged_answers = dict(active_session.answers)
        normalized_answers = _normalized_answer_map(request_body.answers)
        merged_answers.update(normalized_answers)
        _log_app_event(
            "workspace.answers",
            payload={
                "proposal_id": active_session.proposal_id,
                "submitted_answer_count": len(normalized_answers),
                "total_answer_count": len(merged_answers),
            },
            console_message=(
                f"workspace.answers proposal_id={active_session.proposal_id} "
                f"submitted={len(normalized_answers)} total={len(merged_answers)}"
            ),
        )
        try:
            result = continue_workspace_stage1_result(
                result=active_session.result,
                answers=normalized_answers,
                workspace_company=active_session.workspace_company,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1ExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Stage1InputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        app.state.proposal_session = WorkspaceProposalSessionState(
            active_session=_workspace_session_with_handoff(
                proposal_id=active_session.proposal_id,
                workspace_company=active_session.workspace_company,
                proposal=active_session.proposal,
                answers=merged_answers,
                result=result,
            )
        )
        return app.state.proposal_session

    @app.post("/api/workspace/proposal/skip", response_model=WorkspaceProposalSessionState)
    def skip_workspace_proposal() -> WorkspaceProposalSessionState:
        active_session = app.state.proposal_session.active_session
        if active_session is None:
            raise HTTPException(
                status_code=409,
                detail="Start a proposal interview before skipping clarification answers.",
            )
        if active_session.result.outcome != "clarification_needed":
            raise HTTPException(
                status_code=409,
                detail="The active proposal is already Stage 1 ready. Reset the interview to start again.",
            )

        result = skip_workspace_stage1_result(active_session.result)
        app.state.proposal_session = WorkspaceProposalSessionState(
            active_session=_workspace_session_with_handoff(
                proposal_id=active_session.proposal_id,
                workspace_company=active_session.workspace_company,
                proposal=active_session.proposal,
                answers=active_session.answers,
                result=result,
            )
        )
        return app.state.proposal_session

    @app.post("/api/workspace/proposal/formalize", response_model=WorkspaceProposalSessionState)
    def formalize_workspace_proposal() -> WorkspaceProposalSessionState:
        active_session = app.state.proposal_session.active_session
        if active_session is None:
            raise HTTPException(
                status_code=409,
                detail="Start a proposal interview before checking the decision.",
            )
        if active_session.result.outcome != "stage1_ready":
            raise HTTPException(
                status_code=409,
                detail="The active proposal must finish Stage 1 before checking the decision.",
            )

        app.state.proposal_session = WorkspaceProposalSessionState(
            active_session=_workspace_session_with_handoff(
                proposal_id=active_session.proposal_id,
                workspace_company=active_session.workspace_company,
                proposal=active_session.proposal,
                answers=active_session.answers,
                result=active_session.result,
            )
        )
        return app.state.proposal_session

    @app.delete("/api/workspace/proposal", response_model=WorkspaceProposalSessionState)
    def reset_workspace_proposal() -> WorkspaceProposalSessionState:
        app.state.proposal_session = WorkspaceProposalSessionState()
        return app.state.proposal_session

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

    @app.get("/landing", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "view": "landing",
                "workspace": app.state.workspace,
                "proposal_session": app.state.proposal_session,
            },
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Response:
        if app.state.workspace.active_company is None:
            return RedirectResponse(url="/landing", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "view": "chat",
                "workspace": app.state.workspace,
                "proposal_session": app.state.proposal_session,
            },
        )

    return app
