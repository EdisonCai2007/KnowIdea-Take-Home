from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from decision_prover.contracts.output import Stage1RunRequest
from decision_prover.fixtures import load_proposals_fixture
from decision_prover.stage1 import Stage1ExecutionError, run_stage1


class FakeClient:
    def __init__(self, responses: list[dict[str, object] | str | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> SimpleNamespace:
        self.calls.append({"messages": messages, "response_format": response_format})
        if not self._responses:
            raise AssertionError("Unexpected Stage 1 planner call.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        raw_model_response = response if isinstance(response, str) else json.dumps(response)
        return SimpleNamespace(raw_model_response=raw_model_response)


def _load_fixture(proposals_path: Path):
    return load_proposals_fixture(proposals_path)


def _fact(value: int | float | str, unit: str, note: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"value": value, "unit": unit}
    if note is not None:
        payload["note"] = note
    return payload


def _constraint(
    constraint_id: str,
    statement: str,
    semi_formal: str,
    note: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": constraint_id,
        "kind": "hard",
        "statement": statement,
        "semi_formal": semi_formal,
    }
    if note is not None:
        payload["note"] = note
    return payload


def _e(
    field: str,
    quote: str,
    *,
    source_type: str = "proposal",
    source_locator: str = "proposal",
) -> dict[str, str]:
    return {
        "field": field,
        "source_type": source_type,
        "source_quote": quote,
        "source_locator": source_locator,
    }


def _gap(category: str, field: str, verification_check: str, reason: str) -> dict[str, str]:
    return {
        "category": category,
        "field": field,
        "verification_check": verification_check,
        "reason": reason,
    }


def _question(
    field: str,
    verification_check: str,
    question: str,
    rationale: str,
) -> dict[str, str]:
    return {
        "field": field,
        "verification_check": verification_check,
        "question": question,
        "rationale": rationale,
    }


def _plan(
    *,
    action_family: str | None,
    scope_status: str = "supported_family",
    ignored_details: list[str] | None = None,
    companies: list[dict[str, object]] | None = None,
    decisions: list[dict[str, object]] | None = None,
    gaps: list[dict[str, str]] | None = None,
    questions: list[dict[str, str]] | None = None,
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "scope_status": scope_status,
        "action_family": action_family,
        "ignored_details": ignored_details or [],
        "companies": companies or [],
        "decisions": decisions or [],
        "gaps": gaps or [],
        "questions": questions or [],
        "evidence": evidence or [],
    }


def _p3_initial_plan() -> dict[str, object]:
    return _plan(
        action_family="one_time_spend",
        companies=[
            {
                "name": None,
                "sector": None,
                "facts": {
                    "cash_balance": _fact(2_000_000, "USD"),
                    "net_monthly_burn": _fact(250_000, "USD/mo"),
                },
                "constraints": [
                    _constraint(
                        "P3-C1",
                        "Forward runway must remain at or above 6 months.",
                        "runway_months(t) = cash_balance(t)/net_burn(t) >= 6  for all t",
                    )
                ],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "one_time_spend",
                    "cash_cost": 1_000_000,
                    "label": "brand_marketing_campaign",
                },
                "objective": "Fund the campaign only if the runway policy is preserved.",
                "stated_assumptions": [],
            }
        ],
        gaps=[
            _gap(
                "company_metadata",
                "company.name",
                "identify_company",
                "The company name is required for final formalization.",
            ),
            _gap(
                "company_metadata",
                "company.sector",
                "identify_sector",
                "The company sector is required for final formalization.",
            ),
        ],
        questions=[
            _question(
                "company.name",
                "identify_company",
                "What is the company name?",
                "The battery document requires an explicit company name.",
            ),
            _question(
                "company.sector",
                "identify_sector",
                "What sector is the company in?",
                "The battery document requires an explicit company sector.",
            ),
        ],
        evidence=[
            _e("companies[0].facts.cash_balance", "$2M in the bank"),
            _e("companies[0].facts.net_monthly_burn", "burning $250k a month"),
            _e(
                "companies[0].constraints[0]",
                "keep at least six months of runway at all times",
            ),
            _e("decisions[0].action.type", "brand-marketing campaign"),
            _e("decisions[0].action.cash_cost", "$1M upfront"),
            _e("decisions[0].action.label", "brand-marketing campaign"),
            _e("decisions[0].objective", "Good idea?"),
        ],
    )


def _p3_formalized_plan() -> dict[str, object]:
    return _plan(
        action_family="one_time_spend",
        companies=[
            {
                "name": "Northwind Software",
                "sector": "B2B SaaS",
                "facts": {
                    "cash_balance": _fact(2_000_000, "USD"),
                    "net_monthly_burn": _fact(250_000, "USD/mo"),
                },
                "constraints": [
                    _constraint(
                        "P3-C1",
                        "Forward runway must remain at or above 6 months.",
                        "runway_months(t) = cash_balance(t)/net_burn(t) >= 6  for all t",
                    )
                ],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "one_time_spend",
                    "cash_cost": 1_000_000,
                    "label": "brand_marketing_campaign",
                },
                "objective": "Fund the campaign only if the runway policy is preserved.",
                "stated_assumptions": [],
            }
        ],
        evidence=[
            _e(
                "companies[0].name",
                "Northwind Software",
                source_type="answer",
                source_locator="P3_Q_company_name",
            ),
            _e(
                "companies[0].sector",
                "B2B SaaS",
                source_type="answer",
                source_locator="P3_Q_company_sector",
            ),
            _e("companies[0].facts.cash_balance", "$2M in the bank"),
            _e("companies[0].facts.net_monthly_burn", "burning $250k a month"),
            _e(
                "companies[0].constraints[0]",
                "keep at least six months of runway at all times",
            ),
            _e("decisions[0].action.type", "brand-marketing campaign"),
            _e("decisions[0].action.cash_cost", "$1M upfront"),
            _e("decisions[0].action.label", "brand-marketing campaign"),
            _e("decisions[0].objective", "Good idea?"),
        ],
    )


def _p4_initial_plan() -> dict[str, object]:
    return _plan(
        action_family="channel_test",
        ignored_details=["we just redesigned our logo and the team loves it"],
        companies=[
            {
                "name": None,
                "sector": None,
                "facts": {
                    "arpu_monthly": _fact(80, "USD/customer/mo"),
                    "gross_margin": _fact(0.75, "fraction"),
                    "monthly_churn_rate": _fact(0.04, "fraction"),
                },
                "constraints": [
                    _constraint(
                        "P4-C1",
                        "A growth channel may only be scaled if its LTV/CAC is at least 3.0.",
                        "ltv_cac(channel) >= 3.0",
                    )
                ],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "channel_test",
                    "projected_cac": 400,
                    "projected_arpu_monthly": 80,
                },
                "objective": "Scale the channel only if it clears the LTV/CAC policy.",
                "stated_assumptions": [],
            }
        ],
        gaps=[
            _gap(
                "company_metadata",
                "company.name",
                "identify_company",
                "The company name is required for final formalization.",
            ),
            _gap(
                "company_metadata",
                "company.sector",
                "identify_sector",
                "The company sector is required for final formalization.",
            ),
        ],
        questions=[
            _question(
                "company.name",
                "identify_company",
                "What is the company name?",
                "The battery document requires an explicit company name.",
            ),
            _question(
                "company.sector",
                "identify_sector",
                "What sector is the company in?",
                "The battery document requires an explicit company sector.",
            ),
        ],
        evidence=[
            _e("companies[0].facts.arpu_monthly", "ARPU is $80 a month"),
            _e("companies[0].facts.gross_margin", "gross margin is 75%"),
            _e("companies[0].facts.monthly_churn_rate", "monthly churn is 4%"),
            _e("companies[0].constraints[0]", "LTV/CAC is at least 3"),
            _e("decisions[0].action.type", "Should we scale this one?"),
            _e("decisions[0].action.projected_cac", "CAC of $400"),
            _e("decisions[0].action.projected_arpu_monthly", "ARPU is $80 a month"),
            _e("decisions[0].objective", "Should we scale this one?"),
        ],
    )


def _p4_broken_grounding_plan() -> dict[str, object]:
    return _plan(
        action_family="channel_test",
        ignored_details=["we just redesigned our logo and the team loves it"],
        companies=[
            {
                "name": "Lighthouse Metrics",
                "sector": "Subscription software",
                "facts": {
                    "arpu_monthly": _fact(80, "USD/customer/mo"),
                    "gross_margin": _fact(0.75, "fraction"),
                    "monthly_churn_rate": _fact(0.04, "fraction"),
                },
                "constraints": [
                    _constraint(
                        "P4-C1",
                        "A growth channel may only be scaled if its LTV/CAC is at least 3.0.",
                        "ltv_cac(channel) >= 3.0",
                    )
                ],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "channel_test",
                    "projected_cac": 400,
                    "projected_arpu_monthly": 80,
                },
                "objective": "Scale the channel only if it clears the LTV/CAC policy.",
                "stated_assumptions": [],
            }
        ],
        evidence=[
            _e(
                "companies[0].name",
                "Lighthouse Metrics",
                source_type="answer",
                source_locator="P4_Q_company_name",
            ),
            _e(
                "companies[0].sector",
                "Subscription software",
                source_type="answer",
                source_locator="P4_Q_company_sector",
            ),
            _e("companies[0].facts.arpu_monthly", "ARPU is $80 a month"),
            _e("companies[0].facts.gross_margin", "gross margin is 75%"),
            _e("companies[0].facts.monthly_churn_rate", "monthly churn is 5%"),
            _e("companies[0].constraints[0]", "LTV/CAC is at least 4"),
            _e("decisions[0].action.type", "Should we scale this one?"),
            _e("decisions[0].action.projected_cac", "CAC of $450"),
            _e("decisions[0].action.projected_arpu_monthly", "ARPU is $80 a month"),
            _e("decisions[0].objective", "Should we scale this one?"),
        ],
    )


def _p5_initial_plan() -> dict[str, object]:
    return _plan(
        action_family="price_change",
        companies=[
            {
                "name": None,
                "sector": None,
                "facts": {},
                "constraints": [],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "price_change",
                    "pct_increase": 0.2,
                },
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
        gaps=[
            _gap(
                "company_metadata",
                "company.name",
                "identify_company",
                "The company name is required for final formalization.",
            ),
            _gap(
                "company_metadata",
                "company.sector",
                "identify_sector",
                "The company sector is required for final formalization.",
            ),
            _gap(
                "action_details",
                "action.scope",
                "formalize_action_payload",
                "The scope of the price change is required for price_change actions.",
            ),
        ],
        questions=[
            _question(
                "company.name",
                "identify_company",
                "What is the company name?",
                "The battery document requires an explicit company name.",
            ),
            _question(
                "company.sector",
                "identify_sector",
                "What sector is the company in?",
                "The battery document requires an explicit company sector.",
            ),
            _question(
                "action.scope",
                "formalize_action_payload",
                "Which plans, products, or customer segments will see the 20% price increase?",
                "Price-change decisions need an explicit scope.",
            ),
        ],
        evidence=[
            _e("decisions[0].action.type", "raise our prices"),
            _e("decisions[0].action.pct_increase", "20%"),
            _e("decisions[0].objective", "boost revenue"),
        ],
    )


def _p5_formalized_plan() -> dict[str, object]:
    return _plan(
        action_family="price_change",
        companies=[
            {
                "name": "Northwind Software",
                "sector": "B2B SaaS",
                "facts": {},
                "constraints": [],
            }
        ],
        decisions=[
            {
                "action": {
                    "type": "price_change",
                    "pct_increase": 0.2,
                    "scope": "new_customers",
                },
                "objective": "Increase revenue through a 20% price increase.",
                "stated_assumptions": [],
            }
        ],
        evidence=[
            _e(
                "companies[0].name",
                "Northwind Software",
                source_type="answer",
                source_locator="P5_Q_company_name",
            ),
            _e(
                "companies[0].sector",
                "B2B SaaS",
                source_type="answer",
                source_locator="P5_Q_company_sector",
            ),
            _e("decisions[0].action.type", "raise our prices"),
            _e("decisions[0].action.pct_increase", "20%"),
            _e(
                "decisions[0].action.scope",
                "new customers only",
                source_type="answer",
                source_locator="P5_Q_action_scope",
            ),
            _e("decisions[0].objective", "boost revenue"),
        ],
    )


def test_stage1_raw_p3_and_p4_require_company_metadata(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_p3_initial_plan(), _p4_initial_plan()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(proposal_ids=["P3", "P4"]),
        client=client,
    )

    assert response.status.state == "stage1_complete"
    assert [result.proposal_id for result in response.results] == ["P3", "P4"]
    for result in response.results:
        assert result.outcome == "clarification_needed"
        assert result.scope_status == "supported_family"
        assert set(result.blocking_fields) == {"company.name", "company.sector"}
        assert {question.id for question in result.questions} == {
            f"{result.proposal_id}_Q_company_name",
            f"{result.proposal_id}_Q_company_sector",
        }


def test_stage1_formalizes_p3_after_company_answers(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_p3_initial_plan(), _p3_formalized_plan()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(
            proposal_ids=["P3"],
            answers={
                "P3": {
                    "P3_Q_company_name": "Northwind Software",
                    "P3_Q_company_sector": "B2B SaaS",
                }
            },
        ),
        client=client,
    )

    result = response.results[0]
    assert result.outcome == "formalized"
    assert result.primary_decision_id == "P3"
    assert result.battery_document.companies[0].name == "Northwind Software"
    assert result.battery_document.companies[0].sector == "B2B SaaS"
    assert result.battery_document.decisions[0].action.type == "one_time_spend"
    assert result.battery_document.decisions[0].action.cash_cost == 1_000_000
    assert result.battery_document.decisions[0].action.label == "brand_marketing_campaign"
    report_entries = {entry.field: entry for entry in result.grounding_report.entries}
    assert report_entries["companies[0].name"].source_type == "answer"
    assert report_entries["companies[0].name"].source_locator == "P3_Q_company_name"
    assert report_entries["companies[0].facts.cash_balance"].source_type == "proposal"
    assert report_entries["decisions[0].action.cash_cost"].source_quote == "$1M upfront"
    assert report_entries["companies[0].constraints[0]"].source_quote.startswith("keep at least")
    assert result.transcript[-1].kind == "formalization"


def test_stage1_requires_grounded_fact_constraint_and_action_evidence(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_p4_initial_plan(), _p4_broken_grounding_plan()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(
            proposal_ids=["P4"],
            answers={
                "P4": {
                    "P4_Q_company_name": "Lighthouse Metrics",
                    "P4_Q_company_sector": "Subscription software",
                }
            },
        ),
        client=client,
    )

    result = response.results[0]
    assert result.outcome == "clarification_needed"
    assert result.ignored_details == ["we just redesigned our logo and the team loves it"]
    assert {
        "company.facts.monthly_churn_rate",
        "company.constraints.ltv_cac_minimum",
        "action.projected_cac",
    }.issubset(set(result.blocking_fields))
    assert {question.id for question in result.questions}.issuperset(
        {
            "P4_Q_company_facts_monthly_churn_rate",
            "P4_Q_company_constraints_ltv_cac_minimum",
            "P4_Q_action_projected_cac",
        }
    )


def test_stage1_returns_scope_clarification_for_unsupported_family(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient(
        [
            _plan(
                action_family=None,
                scope_status="unsupported_family",
                gaps=[
                    _gap(
                        "scope",
                        "scope",
                        "select_supported_action_family",
                        "The proposal does not map to a supported action family yet.",
                    )
                ],
                questions=[
                    _question(
                        "scope",
                        "select_supported_action_family",
                        "Which supported action family is this closest to?",
                        "Stage 1 is verifier-scoped.",
                    )
                ],
            )
        ]
    )

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(proposal_ids=["P1"]),
        client=client,
    )

    result = response.results[0]
    assert result.outcome == "clarification_needed"
    assert result.scope_status == "unsupported_family"
    assert "scope" in result.blocking_fields
    assert result.questions[0].id == "P1_Q_scope"


def test_stage1_rejects_invalid_planner_json(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient(['{"scope_status": 123}'])

    with pytest.raises(Stage1ExecutionError, match="invalid Stage 1 planner JSON"):
        run_stage1(proposal_fixture, Stage1RunRequest(proposal_ids=["P1"]), client=client)


def test_stage1_wraps_provider_failure(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    OpenRouterError = type("OpenRouterError", (RuntimeError,), {})
    client = FakeClient([OpenRouterError("provider unavailable")])

    with pytest.raises(Stage1ExecutionError, match="provider unavailable"):
        run_stage1(proposal_fixture, Stage1RunRequest(proposal_ids=["P1"]), client=client)


def test_stage1_answer_loop_formalizes_price_change_scope(proposals_path: Path) -> None:
    proposal_fixture = _load_fixture(proposals_path)
    client = FakeClient([_p5_initial_plan(), _p5_formalized_plan()])

    response = run_stage1(
        proposal_fixture,
        Stage1RunRequest(
            proposal_ids=["P5"],
            answers={
                "P5": {
                    "P5_Q_company_name": "Northwind Software",
                    "P5_Q_company_sector": "B2B SaaS",
                    "P5_Q_action_scope": "new customers only",
                }
            },
        ),
        client=client,
    )

    result = response.results[0]
    assert result.outcome == "formalized"
    assert result.battery_document.decisions[0].action.type == "price_change"
    assert result.battery_document.decisions[0].action.scope == "new_customers"
    assert any(turn.question_id == "P5_Q_action_scope" for turn in result.transcript)
    assert json.loads(client.calls[1]["messages"][1]["content"])["prior_answers"] == [
        {
            "question_id": "P5_Q_company_name",
            "field": "company.name",
            "question": "What is the company name?",
            "answer": "Northwind Software",
        },
        {
            "question_id": "P5_Q_company_sector",
            "field": "company.sector",
            "question": "What sector is the company in?",
            "answer": "B2B SaaS",
        },
        {
            "question_id": "P5_Q_action_scope",
            "field": "action.scope",
            "question": "Which plans, products, or customer segments will see the 20% price increase?",
            "answer": "new customers only",
        },
    ]
