from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import __version__
from ..constants import DEFAULT_BATTERY_PATH, DEFAULT_PROPOSALS_PATH
from ..contracts.battery import DecisionBattery
from ..contracts.context import DecisionContextList
from ..fixtures import LoadedBattery, load_battery_fixture, load_proposals_fixture
from ..proposals import ProposalFixture

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

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/battery", response_model=DecisionBattery)
    def get_battery() -> DecisionBattery:
        return app.state.loaded_battery.fixture

    @app.get("/api/battery/contexts", response_model=DecisionContextList)
    def get_battery_contexts() -> DecisionContextList:
        return DecisionContextList(root=app.state.loaded_battery.decision_contexts)

    @app.get("/api/proposals", response_model=ProposalFixture)
    def get_proposals() -> ProposalFixture:
        return app.state.proposal_fixture

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "battery": app.state.loaded_battery.fixture,
                "battery_input": app.state.battery_input,
                "proposal_fixture": app.state.proposal_fixture,
                "proposal_input": app.state.proposal_input,
                "decision_contexts": app.state.loaded_battery.decision_contexts,
            },
        )

    return app
