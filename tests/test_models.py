import pytest
from pydantic import ValidationError

from decision_prover.contracts.actions import GenericActionPayload, PriceChangeAction
from decision_prover.contracts.battery import CompanyFact, Constraint, Decision, StatedAssumption
from decision_prover.contracts.workspace import WorkspaceCompanyProfile, WorkspaceProposalSubmitRequest


def _decision_payload(action: dict) -> dict:
    return {
        "id": "T1",
        "company": "lumen",
        "proposal": "Test proposal",
        "action": action,
        "objective": "Test objective",
        "stated_assumptions": [],
    }


def test_fact_requires_value_and_unit() -> None:
    CompanyFact.model_validate({"value": 10, "unit": "USD"})

    with pytest.raises(ValidationError):
        CompanyFact.model_validate({"value": 10})

    with pytest.raises(ValidationError):
        CompanyFact.model_validate({"unit": "USD"})


def test_assumption_status_is_restricted() -> None:
    StatedAssumption.model_validate(
        {"id": "A1", "statement": "Projected CAC holds", "status": "projected"}
    )

    with pytest.raises(ValidationError):
        StatedAssumption.model_validate(
            {"id": "A1", "statement": "Projected CAC holds", "status": "guessed"}
        )


def test_constraint_kind_is_restricted() -> None:
    Constraint.model_validate(
        {
            "id": "C1",
            "kind": "hard",
            "statement": "Cash must stay above zero.",
            "semi_formal": "cash_balance(t) >= 0",
        }
    )

    with pytest.raises(ValidationError):
        Constraint.model_validate(
            {
                "id": "C1",
                "kind": "soft",
                "statement": "Cash should stay high.",
                "semi_formal": "cash_balance(t) >= 0",
            }
        )


def test_known_action_types_validate_explicitly() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "hire",
                "count": 3,
                "role": "engineer",
                "fully_loaded_cost_per_year": 180000,
            }
        )
    )
    assert decision.action.type == "hire"
    assert decision.action.count == 3


def test_known_action_types_allow_partial_payloads() -> None:
    decision = Decision.model_validate(_decision_payload({"type": "hire"}))

    assert decision.action.type == "hire"
    assert decision.action.count is None
    assert decision.action.role is None
    assert decision.action.fully_loaded_cost_per_year is None


def test_channel_test_allows_missing_budget() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "channel_test",
                "projected_cac": 400,
                "projected_arpu_monthly": 80,
            }
        )
    )
    assert decision.action.type == "channel_test"
    assert decision.action.budget is None


def test_one_time_spend_validates_explicitly() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "one_time_spend",
                "cash_cost": 1_000_000,
                "label": "brand_marketing_campaign",
            }
        )
    )
    assert decision.action.type == "one_time_spend"
    assert decision.action.cash_cost == 1_000_000


def test_price_change_accepts_percentage_shape() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "price_change",
                "pct_increase": 0.1,
                "scope": "all plans",
            }
        )
    )
    assert isinstance(decision.action, PriceChangeAction)
    assert decision.action.scope == "all plans"


def test_price_change_accepts_unit_price_shape() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "price_change",
                "new_unit_price": 95,
                "assumed_volume_multiplier": 0.9,
            }
        )
    )
    assert isinstance(decision.action, PriceChangeAction)
    assert decision.action.new_unit_price == 95


def test_price_change_accepts_partial_percentage_shape() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "price_change",
                "pct_increase": 0.1,
            }
        )
    )

    assert isinstance(decision.action, PriceChangeAction)
    assert decision.action.pct_increase == 0.1
    assert decision.action.scope is None


def test_price_change_rejects_mixed_shapes() -> None:
    with pytest.raises(ValidationError):
        Decision.model_validate(
            _decision_payload(
                {
                    "type": "price_change",
                    "pct_increase": 0.1,
                    "scope": "all plans",
                    "new_unit_price": 95,
                    "assumed_volume_multiplier": 0.9,
                }
            )
        )


def test_generic_action_requires_valid_extras() -> None:
    decision = Decision.model_validate(
        _decision_payload(
            {
                "type": "custom_action",
                "budget": 5000,
                "channels": ["events", "email"],
            }
        )
    )
    assert isinstance(decision.action, GenericActionPayload)

    with pytest.raises(ValidationError):
        Decision.model_validate(_decision_payload({"type": "custom_action"}))

    with pytest.raises(ValidationError):
        Decision.model_validate(
            _decision_payload({"type": "custom_action", "unsupported": {"bad": {1, 2, 3}}})
        )


def test_workspace_company_profile_normalizes_and_validates_text() -> None:
    profile = WorkspaceCompanyProfile.model_validate(
        {
            "name": "  Northwind Software  ",
            "sector": "  B2B SaaS ",
            "description": "   ",
        }
    )
    assert profile.name == "Northwind Software"
    assert profile.sector == "B2B SaaS"
    assert profile.description is None

    with pytest.raises(ValidationError):
        WorkspaceCompanyProfile.model_validate(
            {
                "name": "   ",
                "sector": "B2B SaaS",
                "description": "Optional copy",
            }
        )


def test_workspace_proposal_submit_request_trims_and_requires_text() -> None:
    request = WorkspaceProposalSubmitRequest.model_validate({"proposal": "  Raise prices by 20%.  "})
    assert request.proposal == "Raise prices by 20%."

    with pytest.raises(ValidationError):
        WorkspaceProposalSubmitRequest.model_validate({"proposal": "   "})
