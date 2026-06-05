from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from decision_prover.web import create_app


def test_web_health_and_data_endpoints(battery_path: Path, proposals_path: Path) -> None:
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

    proposals = client.get("/api/proposals")
    assert proposals.status_code == 200
    assert len(proposals.json()["proposals"]) == 6


def test_web_index_renders_fixture_summary(battery_path: Path, proposals_path: Path) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Decision Prover" in response.text
    assert "Normalized Contexts" in response.text
