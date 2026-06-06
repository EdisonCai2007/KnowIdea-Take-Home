from pathlib import Path

from decision_prover.contracts.output import Classification
from decision_prover.fixtures import get_decision_context, load_battery_fixture
from decision_prover.verifier import verify_decision


def _context(battery_path: Path, decision_id: str):
    loaded = load_battery_fixture(battery_path)
    return get_decision_context(loaded, decision_id).model_copy(deep=True)


def test_verifier_routes_all_battery_contexts_without_crashing(battery_path: Path) -> None:
    loaded = load_battery_fixture(battery_path)

    for context in loaded.decision_contexts:
        result = verify_decision(context)
        assert result.classification in {
            Classification.SUPPORTED,
            Classification.REFUTED,
            Classification.UNDECIDABLE,
        }


def test_full_battery_classification_regression(battery_path: Path) -> None:
    expected = {
        "D1": Classification.UNDECIDABLE,
        "D2": Classification.SUPPORTED,
        "D3": Classification.REFUTED,
        "D4": Classification.UNDECIDABLE,
        "D5": Classification.REFUTED,
        "D6": Classification.SUPPORTED,
        "D7": Classification.REFUTED,
        "D8": Classification.UNDECIDABLE,
        "D9": Classification.REFUTED,
        "D10": Classification.UNDECIDABLE,
        "D11": Classification.SUPPORTED,
        "D12": Classification.UNDECIDABLE,
    }

    for decision_id, classification in expected.items():
        assert verify_decision(_context(battery_path, decision_id)).classification == classification


def test_d2_is_supported_with_ltv_cac_assumptions(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D2"))

    assert result.classification == Classification.SUPPORTED
    assert [item.id for item in result.binding_constraints] == ["L-C1", "L-C2", "L-C3", "L-C4"]
    assert [item.id for item in result.load_bearing_assumptions] == ["A1", "A2"]


def test_d3_is_refuted_by_first_failed_constraint(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D3"))

    assert result.classification == Classification.REFUTED
    assert [item.id for item in result.binding_constraints] == ["L-C1", "L-C2"]
    assert result.binding_constraints[1].passed is False
    assert "L-C2" in result.refutation.failure_conditions


def test_d1_is_undecidable_on_unquantified_hire_productivity(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D1"))

    assert result.classification == Classification.UNDECIDABLE
    assert result.derivation[-1].rule == "check_hire_objective"
    assert result.pivotal_assumption is not None
    assert result.flip_threshold is not None
    assert result.supported_if is not None
    assert result.refuted_if is not None


def test_partial_action_returns_undecidable_missing_verifier_inputs(battery_path: Path) -> None:
    context = _context(battery_path, "D1")
    context.action.count = None
    context.action.fully_loaded_cost_per_year = None

    result = verify_decision(context)

    assert result.classification == Classification.UNDECIDABLE
    assert result.derivation[-1].rule == "missing_verifier_inputs"
    assert result.derivation[-1].inputs["missing_fields"] == [
        "action.count",
        "action.fully_loaded_cost_per_year",
    ]
    assert "missing proof input(s)" in result.refutation.failure_conditions


def test_cash_reserve_floor_failure_is_refuted(battery_path: Path) -> None:
    context = _context(battery_path, "D3")
    context.action.cash_cost = 2_800_000

    result = verify_decision(context)

    assert result.classification == Classification.REFUTED
    assert result.binding_constraints[0].id == "L-C1"
    assert result.binding_constraints[0].passed is False


def test_runway_floor_failure_is_refuted(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D3"))

    assert result.classification == Classification.REFUTED
    assert result.binding_constraints[1].id == "L-C2"
    assert result.binding_constraints[1].passed is False


def test_initiative_budget_failure_is_refuted(battery_path: Path) -> None:
    context = _context(battery_path, "D12")
    context.action.cost = 3_500_000

    result = verify_decision(context)

    assert result.classification == Classification.REFUTED
    assert [item.id for item in result.binding_constraints] == ["T-C3"]
    assert result.binding_constraints[0].passed is False


def test_ltv_cac_failure_is_refuted(battery_path: Path) -> None:
    context = _context(battery_path, "D2")
    context.action.projected_cac = 16_000

    result = verify_decision(context)

    assert result.classification == Classification.REFUTED
    assert result.binding_constraints[-1].id == "L-C4"
    assert result.binding_constraints[-1].passed is False


def test_append_only_derivation_ordering_is_deterministic(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D1"))

    assert [step.rule for step in result.derivation] == [
        "compute_action_impact",
        "check_cash_reserve_floor",
        "check_runway_floor",
        "check_initiative_budget",
        "check_hire_objective",
    ]


def test_hard_constraint_short_circuit_stops_after_first_failure(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D3"))

    assert [item.id for item in result.binding_constraints] == ["L-C1", "L-C2"]
    assert all(item.id != "L-C3" for item in result.binding_constraints)


def test_accept_order_backlog_feasibility_failure_is_refuted(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D5"))

    assert result.classification == Classification.REFUTED
    assert result.binding_constraints[-1].id == "H-C5"
    assert result.binding_constraints[-1].passed is False
    capacity_step = next(step for step in result.derivation if step.rule == "check_capacity_backlog")
    assert capacity_step.result["achievable_units_by_deadline"] == 125
    assert capacity_step.result["required_units_by_deadline"] == 600


def test_capex_expansion_restores_backlog_feasibility(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D6"))

    assert result.classification == Classification.SUPPORTED
    assert [item.id for item in result.binding_constraints] == ["H-C1", "H-C3", "H-C5"]
    assert result.binding_constraints[-1].passed is True
    assert [item.id for item in result.load_bearing_assumptions] == ["A1"]
    capacity_step = next(step for step in result.derivation if step.rule == "check_capacity_backlog")
    assert capacity_step.result["achievable_units_by_deadline"] == 220
    assert capacity_step.result["required_units_by_deadline"] == 200


def test_new_sku_margin_hurdle_failure_is_refuted(battery_path: Path) -> None:
    context = _context(battery_path, "D8")
    context.action.contribution_margin = 0.20

    result = verify_decision(context)

    assert result.classification == Classification.REFUTED
    assert result.binding_constraints[0].id == "T-C6"
    assert result.binding_constraints[0].passed is False


def test_marketing_spend_cap_failure_is_refuted(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D9"))

    assert result.classification == Classification.REFUTED
    assert [item.id for item in result.binding_constraints] == ["T-C3", "T-C7"]
    marketing_step = next(step for step in result.derivation if step.rule == "check_marketing_spend_cap")
    assert marketing_step.result["total_marketing_spend"] == 900000
    assert marketing_step.result["cap"] == 600000


def test_supply_constrained_price_cut_is_dominated(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D7"))

    assert result.classification == Classification.REFUTED
    dominance_step = next(
        step for step in result.derivation if step.rule == "check_supply_constrained_price_dominance"
    )
    assert dominance_step.result["baseline_fulfilled_units_monthly"] == 25
    assert dominance_step.result["proposed_fulfilled_units_monthly"] == 25
    assert dominance_step.result["dominated"] is True


def test_retention_program_supports_objective_with_improved_ltv(battery_path: Path) -> None:
    result = verify_decision(_context(battery_path, "D11"))

    assert result.classification == Classification.SUPPORTED
    retention_step = next(
        step for step in result.derivation if step.rule == "check_retention_program_objective"
    )
    assert retention_step.result["ltv_before"] == 44800
    assert retention_step.result["ltv_after"] == 56000
    assert retention_step.result["objective_satisfied"] is True


def test_undecidable_results_include_complete_payload(battery_path: Path) -> None:
    for decision_id in ["D1", "D4", "D8", "D10", "D12"]:
        result = verify_decision(_context(battery_path, decision_id))

        assert result.classification == Classification.UNDECIDABLE
        assert result.pivotal_assumption
        assert result.flip_threshold is not None
        assert result.supported_if
        assert result.refuted_if
