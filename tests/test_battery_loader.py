import json
from pathlib import Path

import pytest

from decision_prover.fixtures import FixtureLoadError, get_decision_context, load_battery_fixture


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2))
    return path


def test_battery_smoke_loads_and_normalizes(battery_path: Path) -> None:
    loaded = load_battery_fixture(battery_path)

    assert len(loaded.fixture.companies) == 3
    assert len(loaded.fixture.decisions) == 12
    assert len(loaded.decision_contexts) == 12
    assert loaded.decision_contexts[0].company.id == "lumen"
    assert loaded.decision_contexts[0].company.constraints

    export_one = loaded.decision_contexts[0].model_dump_json(by_alias=True)
    export_two = loaded.decision_contexts[0].model_dump_json(by_alias=True)
    assert export_one == export_two


def test_get_decision_context_returns_requested_record(battery_path: Path) -> None:
    loaded = load_battery_fixture(battery_path)
    context = get_decision_context(loaded, "D6")
    assert context.id == "D6"
    assert context.company.id == "harvest"


def test_duplicate_decision_ids_are_rejected(battery_data: dict, tmp_path: Path) -> None:
    battery_data["decisions"][1]["id"] = battery_data["decisions"][0]["id"]
    fixture_path = _write_json(tmp_path / "duplicate_decision.json", battery_data)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_battery_fixture(fixture_path)

    assert "decisions[1].id" in str(exc_info.value)
    assert "duplicate decision id" in str(exc_info.value)


def test_unknown_company_reference_is_rejected(battery_data: dict, tmp_path: Path) -> None:
    battery_data["decisions"][0]["company"] = "missing-company"
    fixture_path = _write_json(tmp_path / "missing_company.json", battery_data)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_battery_fixture(fixture_path)

    assert "decisions[0].company" in str(exc_info.value)
    assert "unknown company reference" in str(exc_info.value)


def test_invalid_assumption_status_is_rejected(battery_data: dict, tmp_path: Path) -> None:
    battery_data["decisions"][1]["stated_assumptions"][0]["status"] = "guessed"
    fixture_path = _write_json(tmp_path / "invalid_assumption.json", battery_data)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_battery_fixture(fixture_path)

    assert "decisions[1].stated_assumptions[0].status" in str(exc_info.value)


def test_malformed_fact_payload_is_rejected(battery_data: dict, tmp_path: Path) -> None:
    del battery_data["companies"][0]["facts"]["mrr"]["unit"]
    fixture_path = _write_json(tmp_path / "malformed_fact.json", battery_data)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_battery_fixture(fixture_path)

    assert "companies[0].facts.mrr.unit" in str(exc_info.value)


def test_broken_top_level_structure_is_rejected(battery_data: dict, tmp_path: Path) -> None:
    del battery_data["companies"]
    fixture_path = _write_json(tmp_path / "broken_top_level.json", battery_data)

    with pytest.raises(FixtureLoadError) as exc_info:
        load_battery_fixture(fixture_path)

    assert "companies" in str(exc_info.value)

