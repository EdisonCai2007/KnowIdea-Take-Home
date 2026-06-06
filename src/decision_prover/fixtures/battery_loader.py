from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from ..contracts.battery import Company, Decision, DecisionBattery
from ..contracts.context import CompanyContext, DecisionContext
from .errors import FixtureLoadError, format_validation_errors


class LoadedBattery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    fixture: DecisionBattery
    decision_contexts: list[DecisionContext]


def _read_json_file(source_path: Path) -> object:
    try:
        return json.loads(source_path.read_text())
    except FileNotFoundError as exc:
        raise FixtureLoadError(source_path, [f"{source_path}: file not found"]) from exc
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(
            source_path,
            [
                f"{source_path}:{exc.lineno}:{exc.colno}: invalid JSON - {exc.msg}",
            ],
        ) from exc


def _build_decision_context(company: Company, decision: Decision) -> DecisionContext:
    company_context = CompanyContext(
        id=company.id,
        name=company.name,
        sector=company.sector,
        facts=company.facts,
        constraints=company.constraints,
    )
    return DecisionContext(
        id=decision.id,
        company=company_context,
        proposal=decision.proposal,
        action=decision.action,
        objective=decision.objective,
        stated_assumptions=decision.stated_assumptions,
    )


def _collect_integrity_problems(source_path: Path, fixture: DecisionBattery) -> list[str]:
    problems: list[str] = []
    company_index: dict[str, int] = {}
    for idx, company in enumerate(fixture.companies):
        if company.id in company_index:
            first = company_index[company.id]
            problems.append(
                f"{source_path}:companies[{idx}].id: duplicate company id '{company.id}' "
                f"(first defined at companies[{first}].id)"
            )
        else:
            company_index[company.id] = idx

    decision_index: dict[str, int] = {}
    for idx, decision in enumerate(fixture.decisions):
        if decision.id in decision_index:
            first = decision_index[decision.id]
            problems.append(
                f"{source_path}:decisions[{idx}].id: duplicate decision id '{decision.id}' "
                f"(first defined at decisions[{first}].id)"
            )
        else:
            decision_index[decision.id] = idx

        if decision.company not in company_index:
            problems.append(
                f"{source_path}:decisions[{idx}].company: unknown company reference "
                f"'{decision.company}'"
            )

    return problems


def _build_loaded_battery(source_path: Path, fixture: DecisionBattery) -> LoadedBattery:
    integrity_problems = _collect_integrity_problems(source_path, fixture)
    if integrity_problems:
        raise FixtureLoadError(source_path, integrity_problems)

    company_lookup = {company.id: company for company in fixture.companies}
    decision_contexts = [
        _build_decision_context(company_lookup[decision.company], decision)
        for decision in fixture.decisions
    ]

    return LoadedBattery(
        source_path=str(source_path.resolve()),
        fixture=fixture,
        decision_contexts=decision_contexts,
    )


def load_battery_document(
    document: object,
    *,
    source_label: str | Path = "<memory-battery>",
) -> LoadedBattery:
    source_path = Path(source_label)

    try:
        fixture = DecisionBattery.model_validate(document)
    except ValidationError as exc:
        raise FixtureLoadError(source_path, format_validation_errors(source_path, exc)) from exc

    return _build_loaded_battery(source_path, fixture)


def load_battery_fixture(input_path: str | Path) -> LoadedBattery:
    source_path = Path(input_path)
    raw_data = _read_json_file(source_path)
    return load_battery_document(raw_data, source_label=source_path)


def get_decision_context(loaded_battery: LoadedBattery, decision_id: str) -> DecisionContext:
    for context in loaded_battery.decision_contexts:
        if context.id == decision_id:
            return context

    source_path = Path(loaded_battery.source_path)
    raise FixtureLoadError(
        source_path,
        [f"{source_path}: decision '{decision_id}' not found in normalized contexts"],
    )
