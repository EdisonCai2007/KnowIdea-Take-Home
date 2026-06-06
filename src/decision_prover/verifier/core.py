from __future__ import annotations

import re
from typing import Callable

from ..contracts.context import DecisionContext
from ..contracts.output import VerificationResult
from .session import ActionImpact, VerificationSession, normalize_number

ConstraintFamily = str

_CASH_RESERVE_FLOOR = "cash_reserve_floor"
_RUNWAY_FLOOR = "runway_floor"
_INITIATIVE_BUDGET = "initiative_budget_cap"
_LTV_CAC_MINIMUM = "ltv_cac_minimum"
_CAPACITY_BACKLOG = "capacity_backlog"
_NEW_SKU_MARGIN = "new_sku_margin"
_MARKETING_SPEND_CAP = "marketing_spend_cap"

_CASH_RESERVE_PATTERN = re.compile(r"cash_balance\(t\)\s*>=\s*([0-9.]+)")
_RUNWAY_PATTERN = re.compile(r"net_burn\(t\)\s*>=\s*([0-9.]+)")
_INITIATIVE_BUDGET_PATTERN = re.compile(r"initiative_budget\s*<=\s*([0-9.]+)")
_LTV_CAC_PATTERN = re.compile(r"ltv_cac\(channel\)\s*>=\s*([0-9.]+)")
_CAPACITY_BACKLOG_PATTERN = re.compile(
    r"cumulative_units_built\(by month\s+([0-9.]+)\)\s*>=\s*([0-9.]+)"
)
_NEW_SKU_MARGIN_PATTERN = re.compile(r"new_sku_contribution_margin\s*>=\s*([0-9.]+)")
_MARKETING_SPEND_CAP_PATTERN = re.compile(
    r"total_marketing_spend\s*<=\s*([0-9.]+)\s*\*\s*monthly_revenue"
)


def verify_decision(context: DecisionContext) -> VerificationResult:
    session = VerificationSession(context=context)

    result = _evaluate_hard_constraints(session)
    if result is not None:
        return result

    result = _evaluate_dominance(session)
    if result is not None:
        return result

    result = _missing_objective_input_result(session)
    if result is not None:
        return result

    return _evaluate_objective(session)


def _evaluate_hard_constraints(session: VerificationSession) -> VerificationResult | None:
    for constraint in session.context.company.constraints:
        family = _classify_constraint(constraint.semi_formal)
        if not _constraint_applies(family, session.context.action.type):
            continue

        missing_result = _missing_constraint_input_result(session, family, constraint.id)
        if missing_result is not None:
            return missing_result

        if family == _CASH_RESERVE_FLOOR:
            result = _check_cash_reserve_floor(session, constraint.id, constraint.semi_formal)
        elif family == _RUNWAY_FLOOR:
            result = _check_runway_floor(session, constraint.id, constraint.semi_formal)
        elif family == _INITIATIVE_BUDGET:
            result = _check_initiative_budget(session, constraint.id, constraint.semi_formal)
        elif family == _LTV_CAC_MINIMUM:
            result = _check_ltv_cac_minimum(session, constraint.id, constraint.semi_formal)
        elif family == _CAPACITY_BACKLOG:
            result = _check_capacity_backlog(session, constraint.id, constraint.semi_formal)
        elif family == _NEW_SKU_MARGIN:
            result = _check_new_sku_margin(session, constraint.id, constraint.semi_formal)
        elif family == _MARKETING_SPEND_CAP:
            result = _check_marketing_spend_cap(session, constraint.id, constraint.semi_formal)
        else:
            result = session.coverage_gap_result(
                stage="hard_constraints",
                reason=f"hard-constraint family '{family}' is not implemented in Phase 2",
                inputs={
                    "constraint_id": constraint.id,
                    "action_type": session.context.action.type,
                },
            )

        if result is not None:
            return result

    return None


def _evaluate_dominance(session: VerificationSession) -> VerificationResult | None:
    if session.context.action.type == "price_change":
        missing_result = _missing_price_dominance_input_result(session)
        if missing_result is not None:
            return missing_result
        return _evaluate_price_change_dominance(session)

    return None


def _missing_constraint_input_result(
    session: VerificationSession,
    family: ConstraintFamily,
    constraint_id: str,
) -> VerificationResult | None:
    action_type = session.context.action.type
    missing: list[str] = []
    if family == _CASH_RESERVE_FLOOR:
        missing.extend(_missing_fact_fields(session.context, ["cash_balance"]))
        missing.extend(_missing_action_fields(session.context, _impact_action_fields(action_type)))
    elif family == _RUNWAY_FLOOR:
        missing.extend(_missing_fact_fields(session.context, ["cash_balance", "net_monthly_burn"]))
        missing.extend(_missing_action_fields(session.context, _impact_action_fields(action_type)))
    elif family == _INITIATIVE_BUDGET:
        missing.extend(_missing_action_fields(session.context, _impact_action_fields(action_type)))
    elif family == _LTV_CAC_MINIMUM:
        missing.extend(_missing_fact_fields(session.context, ["gross_margin", "monthly_churn_rate"]))
        missing.extend(_missing_action_fields(session.context, ["projected_cac", "projected_arpu_monthly"]))
    elif family == _CAPACITY_BACKLOG:
        missing.extend(_missing_fact_fields(session.context, ["production_capacity", "backlog_units"]))
        if action_type == "accept_order":
            missing.extend(_missing_action_fields(session.context, ["units", "due_months"]))
        elif action_type == "capex_expansion":
            missing.extend(
                _missing_action_fields(
                    session.context,
                    ["capacity_from", "capacity_to", "ramp_months"],
                )
            )
    elif family == _NEW_SKU_MARGIN:
        missing.extend(_missing_action_fields(session.context, ["contribution_margin"]))
    elif family == _MARKETING_SPEND_CAP:
        missing.extend(
            _missing_fact_fields(session.context, ["current_marketing_spend", "monthly_revenue"])
        )
        missing.extend(_missing_action_fields(session.context, ["added_monthly_spend"]))

    if not missing:
        return None
    return _missing_input_result(
        session,
        stage="hard_constraints",
        missing_fields=missing,
        constraint_id=constraint_id,
    )


def _missing_price_dominance_input_result(session: VerificationSession) -> VerificationResult | None:
    action = session.context.action
    new_unit_price = getattr(action, "new_unit_price", None)
    assumed_volume_multiplier = getattr(action, "assumed_volume_multiplier", None)
    if new_unit_price is None and assumed_volume_multiplier is None:
        return None
    if new_unit_price is None or assumed_volume_multiplier is None:
        return _missing_input_result(
            session,
            stage="dominance",
            missing_fields=_missing_action_fields(
                session.context,
                ["new_unit_price", "assumed_volume_multiplier"],
            ),
        )

    missing = _missing_fact_fields(
        session.context,
        [
            "demand_status",
            "unit_sale_price",
            "production_capacity",
            "unit_gross_margin",
            "unit_bom_cost",
        ],
    )
    if not missing:
        return None
    return _missing_input_result(
        session,
        stage="dominance",
        missing_fields=missing,
    )


def _missing_objective_input_result(session: VerificationSession) -> VerificationResult | None:
    action_type = session.context.action.type
    missing: list[str] = []
    if action_type == "acquisition":
        missing.extend(_missing_action_fields(session.context, ["added_mrr"]))
    elif action_type == "hire":
        missing.extend(_missing_fact_fields(session.context, ["headcount"]))
        missing.extend(
            _missing_action_fields(
                session.context,
                ["count", "fully_loaded_cost_per_year"],
            )
        )
    elif action_type == "price_change":
        action = session.context.action
        if getattr(action, "pct_increase", None) is not None or getattr(action, "scope", None) is not None:
            missing.extend(_missing_action_fields(session.context, ["pct_increase", "scope"]))
    elif action_type == "launch_sku":
        missing.extend(_missing_action_fields(session.context, ["projected_monthly_revenue"]))
    elif action_type == "discontinue_line":
        missing.extend(_missing_fact_fields(session.context, ["line_B_revenue", "line_B_contribution_margin"]))
    elif action_type == "retention_program":
        missing.extend(_missing_fact_fields(session.context, ["gross_margin", "arpu_monthly"]))
        missing.extend(_missing_action_fields(session.context, ["churn_from", "churn_to"]))
    elif action_type == "supplier_renegotiation":
        missing.extend(_missing_fact_fields(session.context, ["line_A_contribution_margin"]))
        missing.extend(_missing_action_fields(session.context, ["line_A_cogs_reduction_pts"]))

    if not missing:
        return None
    return _missing_input_result(
        session,
        stage="objective_satisfaction",
        missing_fields=missing,
    )


def _missing_action_fields(context: DecisionContext, fields: list[str] | set[str]) -> list[str]:
    missing = []
    for field in sorted(fields):
        if getattr(context.action, field, None) is None:
            missing.append(f"action.{field}")
    return missing


def _missing_fact_fields(context: DecisionContext, fields: list[str]) -> list[str]:
    missing = []
    for field in fields:
        fact = context.company.facts.get(field)
        if fact is None or fact.value is None:
            missing.append(f"company.facts.{field}")
    return missing


def _missing_input_result(
    session: VerificationSession,
    *,
    stage: str,
    missing_fields: list[str],
    constraint_id: str | None = None,
) -> VerificationResult:
    ordered = sorted(dict.fromkeys(missing_fields))
    inputs = {
        "stage": stage,
        "action_type": session.context.action.type,
        "missing_fields": ordered,
    }
    if constraint_id is not None:
        inputs["constraint_id"] = constraint_id
    reason = "missing proof input(s): " + ", ".join(ordered)
    session.add_step("missing_verifier_inputs", inputs, reason)
    return session.undecidable_result(
        pivotal_assumption="Required proof inputs are missing from the formalized decision.",
        flip_threshold="Provide the missing input(s) so the verifier can compute the verdict boundary.",
        supported_if="the missing inputs satisfy every applicable constraint and objective check",
        refuted_if="the missing inputs violate an applicable constraint or objective check",
        failure_conditions=reason,
    )


def _evaluate_objective(session: VerificationSession) -> VerificationResult:
    action_type = session.context.action.type

    if action_type == "channel_test":
        return _evaluate_channel_test_objective(session)

    if action_type == "acquisition":
        return _evaluate_acquisition_objective(session)

    if action_type == "hire":
        return _evaluate_hire_objective(session)

    if action_type == "price_change":
        return _evaluate_price_change_objective(session)

    if action_type == "capex_expansion":
        return _evaluate_capex_expansion_objective(session)

    if action_type == "launch_sku":
        return _evaluate_launch_sku_objective(session)

    if action_type == "discontinue_line":
        return _evaluate_discontinue_line_objective(session)

    if action_type == "retention_program":
        return _evaluate_retention_program_objective(session)

    if action_type == "supplier_renegotiation":
        return _evaluate_supplier_renegotiation_objective(session)

    return session.coverage_gap_result(
        stage="objective_satisfaction",
        reason=f"objective evaluator not implemented for action type '{action_type}'",
        inputs={"action_type": action_type},
    )


def _evaluate_channel_test_objective(session: VerificationSession) -> VerificationResult:
    checked_ltv_cac = any(
        _classify_constraint(constraint.semi_formal) == _LTV_CAC_MINIMUM
        and any(binding.id == constraint.id and binding.passed for binding in session.binding_constraints)
        for constraint in session.context.company.constraints
    )
    if not checked_ltv_cac:
        return session.coverage_gap_result(
            stage="objective_satisfaction",
            reason="channel-test objective requires a checked LTV/CAC hard constraint",
            inputs={"action_type": session.context.action.type},
        )

    session.add_projected_assumptions()
    session.add_step(
        "check_channel_test_objective",
        {
            "objective": session.context.objective,
            "ltv_cac_constraint_checked": checked_ltv_cac,
        },
        "supported under Phase 2 channel-test objective policy",
    )
    return session.supported_result()


def _evaluate_acquisition_objective(session: VerificationSession) -> VerificationResult:
    added_mrr = float(getattr(session.context.action, "added_mrr"))
    passed = added_mrr > 0
    result = {
        "added_mrr": normalize_number(added_mrr),
        "objective_satisfied": passed,
    }
    session.add_step(
        "check_acquisition_objective",
        {"objective": session.context.objective},
        result,
    )

    if not passed:
        message = "acquisition objective failed: added_mrr must be positive"
        return session.refuted_result(failure_conditions=message)

    return session.supported_result()


def _evaluate_hire_objective(session: VerificationSession) -> VerificationResult:
    headcount_added = int(getattr(session.context.action, "count"))
    annual_cost = float(getattr(session.context.action, "fully_loaded_cost_per_year"))
    session.add_step(
        "check_hire_objective",
        {
            "objective": session.context.objective,
            "current_headcount": normalize_number(_get_numeric_fact(session.context, "headcount")),
        },
        {
            "headcount_added": headcount_added,
            "annual_cost_per_hire": normalize_number(annual_cost),
            "objective_forced_by_facts": False,
        },
    )
    return session.undecidable_result(
        pivotal_assumption=(
            "The five additional engineers materially increase product velocity enough to justify"
            " the hire."
        ),
        flip_threshold=(
            "Product-velocity improvement threshold is not quantified in the provided facts."
        ),
        supported_if="the added engineering capacity yields a material product-velocity gain",
        refuted_if="the added engineering capacity does not produce a material velocity gain",
        failure_conditions=(
            "objective depends on unquantified engineering productivity and delivery impact"
        ),
    )


def _evaluate_price_change_objective(session: VerificationSession) -> VerificationResult:
    action = session.context.action
    if getattr(action, "pct_increase", None) is not None and getattr(action, "scope", None) is not None:
        session.add_assumption("A1")
        session.add_step(
            "check_price_change_objective",
            {
                "objective": session.context.objective,
                "scope": getattr(action, "scope"),
            },
            {
                "pct_increase": normalize_number(float(getattr(action, "pct_increase"))),
                "objective_forced_by_facts": False,
            },
        )
        return session.undecidable_result(
            pivotal_assumption=(
                "New-customer conversion and CAC remain strong enough after the price increase"
                " to improve unit economics."
            ),
            flip_threshold=(
                "The verdict flips at the elasticity/CAC point where the 15% price increase no"
                " longer improves new-business unit economics."
            ),
            supported_if=(
                "the price increase does not worsen conversion or CAC enough to erase the higher"
                " revenue per new customer"
            ),
            refuted_if=(
                "the price increase worsens conversion or CAC enough to offset or reverse the"
                " unit-economics gain"
            ),
            failure_conditions=(
                "objective depends on unmeasured new-customer elasticity and CAC response"
            ),
        )

    return session.coverage_gap_result(
        stage="objective_satisfaction",
        reason="price-change objective evaluator only covers the new-customer elasticity case",
        inputs={"action_type": session.context.action.type},
    )


def _evaluate_capex_expansion_objective(session: VerificationSession) -> VerificationResult:
    session.add_assumption("A1")
    restored_feasibility = session.binding_constraint_passed("H-C5")
    session.add_step(
        "check_capex_expansion_objective",
        {"objective": session.context.objective},
        {"restored_delivery_feasibility": restored_feasibility},
    )
    if not restored_feasibility:
        return session.refuted_result(
            failure_conditions="capacity expansion objective failed: backlog feasibility was not restored"
        )
    return session.supported_result()


def _evaluate_launch_sku_objective(session: VerificationSession) -> VerificationResult:
    projected_incremental_revenue = float(getattr(session.context.action, "projected_monthly_revenue"))
    session.add_assumption("A1")
    session.add_step(
        "check_launch_sku_objective",
        {"objective": session.context.objective},
        {
            "projected_incremental_revenue": normalize_number(projected_incremental_revenue),
            "objective_forced_by_facts": False,
        },
    )
    return session.undecidable_result(
        pivotal_assumption=(
            "Cannibalized premium-line revenue is low enough that the new SKU grows premium"
            " revenue on net."
        ),
        flip_threshold={
            "metric": "cannibalized_premium_revenue_monthly",
            "support_if": f"< {normalize_number(projected_incremental_revenue)}",
            "refute_if": f">= {normalize_number(projected_incremental_revenue)}",
        },
        supported_if=(
            f"cannibalized premium revenue stays below {normalize_number(projected_incremental_revenue)}/mo"
        ),
        refuted_if=(
            f"cannibalized premium revenue reaches or exceeds {normalize_number(projected_incremental_revenue)}/mo"
        ),
        failure_conditions="objective depends on unspecified cannibalization of the existing premium line",
    )


def _evaluate_discontinue_line_objective(session: VerificationSession) -> VerificationResult:
    line_b_revenue = _get_numeric_fact(session.context, "line_B_revenue")
    line_b_margin = _get_numeric_fact(session.context, "line_B_contribution_margin")
    lost_contribution = line_b_revenue * line_b_margin
    session.add_assumption("A1")
    session.add_step(
        "check_discontinue_line_objective",
        {"objective": session.context.objective},
        {
            "lost_line_b_contribution_monthly": normalize_number(lost_contribution),
            "objective_forced_by_facts": False,
        },
    )
    return session.undecidable_result(
        pivotal_assumption=(
            "Reallocated Line A resources generate enough incremental contribution to exceed the"
            " lost Line B contribution."
        ),
        flip_threshold={
            "metric": "incremental_line_a_contribution_monthly",
            "support_if": f"> {normalize_number(lost_contribution)}",
            "refute_if": f"<= {normalize_number(lost_contribution)}",
        },
        supported_if=(
            f"reallocated Line A contribution exceeds {normalize_number(lost_contribution)}/mo"
        ),
        refuted_if=(
            f"reallocated Line A contribution is at or below {normalize_number(lost_contribution)}/mo"
        ),
        failure_conditions="objective depends on unquantified returns from reallocating Line B resources",
    )


def _evaluate_retention_program_objective(session: VerificationSession) -> VerificationResult:
    gross_margin = _get_numeric_fact(session.context, "gross_margin")
    arpu = _get_numeric_fact(session.context, "arpu_monthly")
    churn_before = float(getattr(session.context.action, "churn_from"))
    churn_after = float(getattr(session.context.action, "churn_to"))
    ltv_before = arpu * gross_margin / churn_before
    ltv_after = arpu * gross_margin / churn_after
    improved = churn_after < churn_before and ltv_after > ltv_before

    session.add_step(
        "check_retention_program_objective",
        {"objective": session.context.objective},
        {
            "churn_before": normalize_number(churn_before),
            "churn_after": normalize_number(churn_after),
            "ltv_before": normalize_number(ltv_before),
            "ltv_after": normalize_number(ltv_after),
            "objective_satisfied": improved,
        },
    )

    if not improved:
        return session.refuted_result(
            failure_conditions="retention objective failed: churn and LTV did not both improve"
        )

    return session.supported_result()


def _evaluate_supplier_renegotiation_objective(session: VerificationSession) -> VerificationResult:
    current_margin = _get_numeric_fact(session.context, "line_A_contribution_margin")
    improvement_points = float(getattr(session.context.action, "line_A_cogs_reduction_pts"))
    projected_margin = current_margin + (improvement_points / 100.0)
    session.add_assumption("A1")
    session.add_step(
        "check_supplier_renegotiation_objective",
        {"objective": session.context.objective},
        {
            "current_line_a_contribution_margin": normalize_number(current_margin),
            "projected_line_a_contribution_margin_if_executed": normalize_number(projected_margin),
            "objective_forced_by_facts": False,
        },
    )
    return session.undecidable_result(
        pivotal_assumption=(
            "The unsigned supplier agreement executes and yields a realized positive Line A margin"
            " improvement."
        ),
        flip_threshold={
            "metric": "realized_line_a_margin_improvement_fraction",
            "support_if": "> 0",
            "refute_if": "<= 0",
        },
        supported_if="the supplier agreement executes and Line A margin improves by more than 0",
        refuted_if="the supplier agreement does not execute or yields no realized margin improvement",
        failure_conditions="objective depends on an unsigned supplier agreement and execution risk",
    )


def _check_cash_reserve_floor(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    impact, gap = _require_action_impact(
        session,
        stage="hard_constraints",
        constraint_id=constraint_id,
    )
    if gap is not None:
        return gap

    current_cash = _get_numeric_fact(session.context, "cash_balance")
    threshold = _extract_threshold(_CASH_RESERVE_PATTERN, expression)
    post_cash = current_cash - impact.cash_outflow

    result = {
        "post_cash_balance": normalize_number(post_cash),
        "threshold": normalize_number(threshold),
        "passed": post_cash >= threshold,
    }
    session.add_step(
        "check_cash_reserve_floor",
        {
            "constraint_id": constraint_id,
            "current_cash_balance": normalize_number(current_cash),
            "cash_outflow": normalize_number(impact.cash_outflow),
        },
        result,
    )

    why = (
        f"post-action cash {normalize_number(post_cash)} >= reserve floor "
        f"{normalize_number(threshold)}"
        if post_cash >= threshold
        else f"post-action cash {normalize_number(post_cash)} < reserve floor "
        f"{normalize_number(threshold)}"
    )
    session.add_binding_constraint(constraint_id, post_cash >= threshold, why)

    if post_cash < threshold:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )

    return None


def _check_runway_floor(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    impact, gap = _require_action_impact(
        session,
        stage="hard_constraints",
        constraint_id=constraint_id,
    )
    if gap is not None:
        return gap

    current_cash = _get_numeric_fact(session.context, "cash_balance")
    current_burn = _get_numeric_fact(session.context, "net_monthly_burn")
    threshold = _extract_threshold(_RUNWAY_PATTERN, expression)
    post_cash = current_cash - impact.cash_outflow
    post_burn = current_burn + impact.monthly_burn_delta
    runway_months = post_cash / post_burn

    result = {
        "post_action_runway_months": normalize_number(runway_months),
        "threshold": normalize_number(threshold),
        "passed": runway_months >= threshold,
    }
    session.add_step(
        "check_runway_floor",
        {
            "constraint_id": constraint_id,
            "post_action_cash_balance": normalize_number(post_cash),
            "post_action_net_monthly_burn": normalize_number(post_burn),
        },
        result,
    )

    why = (
        f"post-action runway {normalize_number(runway_months)} months >= floor "
        f"{normalize_number(threshold)}"
        if runway_months >= threshold
        else f"post-action runway {normalize_number(runway_months)} months < floor "
        f"{normalize_number(threshold)}"
    )
    session.add_binding_constraint(constraint_id, runway_months >= threshold, why)

    if runway_months < threshold:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )

    return None


def _check_initiative_budget(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    impact, gap = _require_action_impact(
        session,
        stage="hard_constraints",
        constraint_id=constraint_id,
    )
    if gap is not None:
        return gap

    threshold = _extract_threshold(_INITIATIVE_BUDGET_PATTERN, expression)
    result = {
        "initiative_budget": normalize_number(impact.initiative_budget),
        "threshold": normalize_number(threshold),
        "passed": impact.initiative_budget <= threshold,
    }
    session.add_step(
        "check_initiative_budget",
        {"constraint_id": constraint_id},
        result,
    )

    why = (
        f"initiative budget {normalize_number(impact.initiative_budget)} <= cap "
        f"{normalize_number(threshold)}"
        if impact.initiative_budget <= threshold
        else f"initiative budget {normalize_number(impact.initiative_budget)} > cap "
        f"{normalize_number(threshold)}"
    )
    session.add_binding_constraint(constraint_id, impact.initiative_budget <= threshold, why)

    if impact.initiative_budget > threshold:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )

    return None


def _check_ltv_cac_minimum(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    threshold = _extract_threshold(_LTV_CAC_PATTERN, expression)
    gross_margin = _get_numeric_fact(session.context, "gross_margin")
    monthly_churn = _get_numeric_fact(session.context, "monthly_churn_rate")
    projected_cac = float(getattr(session.context.action, "projected_cac"))
    projected_arpu = float(getattr(session.context.action, "projected_arpu_monthly"))
    ltv = projected_arpu * gross_margin / monthly_churn
    ratio = ltv / projected_cac

    session.add_projected_assumptions()
    result = {
        "ltv": normalize_number(ltv),
        "cac": normalize_number(projected_cac),
        "ltv_cac_ratio": normalize_number(ratio),
        "threshold": normalize_number(threshold),
        "passed": ratio >= threshold,
    }
    session.add_step(
        "check_ltv_cac_minimum",
        {
            "constraint_id": constraint_id,
            "gross_margin": normalize_number(gross_margin),
            "monthly_churn_rate": normalize_number(monthly_churn),
            "projected_arpu_monthly": normalize_number(projected_arpu),
        },
        result,
    )

    why = (
        f"projected LTV/CAC {normalize_number(ratio)} >= minimum {normalize_number(threshold)}"
        if ratio >= threshold
        else f"projected LTV/CAC {normalize_number(ratio)} < minimum {normalize_number(threshold)}"
    )
    session.add_binding_constraint(constraint_id, ratio >= threshold, why)

    if ratio < threshold:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )

    return None


def _check_capacity_backlog(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    action = session.context.action
    deadline_months, backlog_threshold = _extract_capacity_backlog_terms(expression)
    current_capacity = _get_numeric_fact(session.context, "production_capacity")
    existing_backlog = _get_numeric_fact(session.context, "backlog_units")

    if action.type == "accept_order":
        required_units = existing_backlog + float(getattr(action, "units"))
        relevant_deadline = float(getattr(action, "due_months"))
        achievable_units = current_capacity * relevant_deadline
        result = {
            "achievable_units_by_deadline": normalize_number(achievable_units),
            "required_units_by_deadline": normalize_number(required_units),
            "decision_deadline_months": normalize_number(relevant_deadline),
            "passed": achievable_units >= required_units,
        }
        session.add_step(
            "check_capacity_backlog",
            {
                "constraint_id": constraint_id,
                "baseline_constraint_deadline_months": normalize_number(deadline_months),
                "baseline_backlog_units": normalize_number(backlog_threshold),
                "existing_backlog_units": normalize_number(existing_backlog),
                "new_order_units": normalize_number(float(getattr(action, "units"))),
            },
            result,
        )
        why = (
            f"capacity can build {normalize_number(achievable_units)} units by month"
            f" {normalize_number(relevant_deadline)} against {normalize_number(required_units)} required"
            if achievable_units >= required_units
            else f"capacity can build only {normalize_number(achievable_units)} units by month"
            f" {normalize_number(relevant_deadline)} against {normalize_number(required_units)} required"
        )
        session.add_binding_constraint(constraint_id, achievable_units >= required_units, why)
        if achievable_units < required_units:
            return session.refuted_result(
                failure_conditions=f"hard constraint {constraint_id} failed: {why}"
            )
        return None

    if action.type == "capex_expansion":
        ramp_months = int(getattr(action, "ramp_months"))
        capacity_from = float(getattr(action, "capacity_from"))
        capacity_to = float(getattr(action, "capacity_to"))
        ramp_output = min(deadline_months, ramp_months) * capacity_from
        post_ramp_months = max(deadline_months - ramp_months, 0)
        expanded_output = post_ramp_months * capacity_to
        achievable_units = ramp_output + expanded_output
        passed = achievable_units >= backlog_threshold
        session.add_assumption("A1")
        result = {
            "achievable_units_by_deadline": normalize_number(achievable_units),
            "required_units_by_deadline": normalize_number(backlog_threshold),
            "deadline_months": normalize_number(deadline_months),
            "passed": passed,
        }
        session.add_step(
            "check_capacity_backlog",
            {
                "constraint_id": constraint_id,
                "ramp_months": ramp_months,
                "capacity_from": normalize_number(capacity_from),
                "capacity_to": normalize_number(capacity_to),
            },
            result,
        )
        why = (
            f"capacity plan delivers {normalize_number(achievable_units)} units by month"
            f" {normalize_number(deadline_months)} against {normalize_number(backlog_threshold)} required"
            if passed
            else f"capacity plan delivers only {normalize_number(achievable_units)} units by month"
            f" {normalize_number(deadline_months)} against {normalize_number(backlog_threshold)} required"
        )
        session.add_binding_constraint(constraint_id, passed, why)
        if not passed:
            return session.refuted_result(
                failure_conditions=f"hard constraint {constraint_id} failed: {why}"
            )
        return None

    return session.coverage_gap_result(
        stage="hard_constraints",
        reason=(
            f"capacity-backlog evaluator does not support action type '{session.context.action.type}'"
        ),
        inputs={"constraint_id": constraint_id, "action_type": session.context.action.type},
    )


def _check_new_sku_margin(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    threshold = _extract_threshold(_NEW_SKU_MARGIN_PATTERN, expression)
    contribution_margin = float(getattr(session.context.action, "contribution_margin"))
    passed = contribution_margin >= threshold
    session.add_step(
        "check_new_sku_margin",
        {"constraint_id": constraint_id},
        {
            "new_sku_contribution_margin": normalize_number(contribution_margin),
            "threshold": normalize_number(threshold),
            "passed": passed,
        },
    )
    why = (
        f"new SKU contribution margin {normalize_number(contribution_margin)} >= hurdle {normalize_number(threshold)}"
        if passed
        else f"new SKU contribution margin {normalize_number(contribution_margin)} < hurdle {normalize_number(threshold)}"
    )
    session.add_binding_constraint(constraint_id, passed, why)
    if not passed:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )
    return None


def _check_marketing_spend_cap(
    session: VerificationSession,
    constraint_id: str,
    expression: str,
) -> VerificationResult | None:
    multiplier = _extract_threshold(_MARKETING_SPEND_CAP_PATTERN, expression)
    current_marketing_spend = _get_numeric_fact(session.context, "current_marketing_spend")
    monthly_revenue = _get_numeric_fact(session.context, "monthly_revenue")
    added_monthly_spend = float(getattr(session.context.action, "added_monthly_spend"))
    total_marketing_spend = current_marketing_spend + added_monthly_spend
    cap = multiplier * monthly_revenue
    passed = total_marketing_spend <= cap
    session.add_step(
        "check_marketing_spend_cap",
        {
            "constraint_id": constraint_id,
            "current_marketing_spend": normalize_number(current_marketing_spend),
            "monthly_revenue": normalize_number(monthly_revenue),
        },
        {
            "added_monthly_spend": normalize_number(added_monthly_spend),
            "total_marketing_spend": normalize_number(total_marketing_spend),
            "cap": normalize_number(cap),
            "passed": passed,
        },
    )
    why = (
        f"total marketing spend {normalize_number(total_marketing_spend)} <= cap {normalize_number(cap)}"
        if passed
        else f"total marketing spend {normalize_number(total_marketing_spend)} > cap {normalize_number(cap)}"
    )
    session.add_binding_constraint(constraint_id, passed, why)
    if not passed:
        return session.refuted_result(
            failure_conditions=f"hard constraint {constraint_id} failed: {why}"
        )
    return None


def _evaluate_price_change_dominance(session: VerificationSession) -> VerificationResult | None:
    action = session.context.action
    new_unit_price = getattr(action, "new_unit_price", None)
    assumed_volume_multiplier = getattr(action, "assumed_volume_multiplier", None)
    if new_unit_price is None or assumed_volume_multiplier is None:
        return None

    demand_status = _get_text_fact(session.context, "demand_status")
    if demand_status != "demand_exceeds_capacity":
        return None

    current_unit_price = _get_numeric_fact(session.context, "unit_sale_price")
    production_capacity = _get_numeric_fact(session.context, "production_capacity")
    current_unit_margin = _get_numeric_fact(session.context, "unit_gross_margin")
    new_unit_margin = float(new_unit_price) - _get_numeric_fact(session.context, "unit_bom_cost")
    baseline_revenue = current_unit_price * production_capacity
    proposed_revenue = float(new_unit_price) * production_capacity
    proposed_improves_revenue = proposed_revenue > baseline_revenue
    proposed_improves_margin = new_unit_margin > current_unit_margin

    session.add_step(
        "check_supply_constrained_price_dominance",
        {
            "objective": session.context.objective,
            "assumed_volume_multiplier": normalize_number(float(assumed_volume_multiplier)),
            "production_capacity": normalize_number(production_capacity),
        },
        {
            "baseline_fulfilled_units_monthly": normalize_number(production_capacity),
            "proposed_fulfilled_units_monthly": normalize_number(production_capacity),
            "baseline_revenue_monthly": normalize_number(baseline_revenue),
            "proposed_revenue_monthly": normalize_number(proposed_revenue),
            "baseline_unit_margin": normalize_number(current_unit_margin),
            "proposed_unit_margin": normalize_number(new_unit_margin),
            "dominated": not proposed_improves_revenue and not proposed_improves_margin,
        },
    )

    if not proposed_improves_revenue and not proposed_improves_margin:
        return session.refuted_result(
            failure_conditions=(
                "baseline dominates: demand already exceeds capacity, so the price cut cannot"
                " increase fulfilled volume and only weakens unit economics"
            )
        )

    return None


def _require_action_impact(
    session: VerificationSession,
    *,
    stage: str,
    constraint_id: str,
) -> tuple[ActionImpact, None] | tuple[None, VerificationResult]:
    impact = _get_action_impact(session)
    if impact is not None:
        return impact, None

    result = session.coverage_gap_result(
        stage=stage,
        reason=f"action impact adapter not implemented for action type '{session.context.action.type}'",
        inputs={
            "constraint_id": constraint_id,
            "action_type": session.context.action.type,
        },
    )
    return None, result


def _get_action_impact(session: VerificationSession) -> ActionImpact | None:
    if session.action_impact is not None:
        return session.action_impact

    builder = _ACTION_IMPACT_BUILDERS.get(session.context.action.type)
    if builder is None:
        return None

    return session.store_action_impact(builder(session.context))


def _impact_action_fields(action_type: str) -> set[str]:
    return {
        "hire": {"count", "fully_loaded_cost_per_year"},
        "channel_test": {"budget"},
        "acquisition": {"cash_cost"},
        "one_time_spend": {"cash_cost"},
        "capex_expansion": {"cost"},
        "launch_sku": {"launch_cost"},
        "retention_program": {"cost"},
        "supplier_renegotiation": {"cost"},
        "marketing_increase": {"added_monthly_spend"},
    }.get(action_type, set())


def _build_hire_impact(context: DecisionContext) -> ActionImpact:
    annual_cost = float(getattr(context.action, "count")) * float(
        getattr(context.action, "fully_loaded_cost_per_year")
    )
    return ActionImpact(
        initiative_budget=annual_cost,
        cash_outflow=0.0,
        monthly_burn_delta=annual_cost / 12.0,
    )


def _build_channel_test_impact(context: DecisionContext) -> ActionImpact:
    raw_budget = getattr(context.action, "budget", None)
    budget = 0.0 if raw_budget is None else float(raw_budget)
    return ActionImpact(initiative_budget=budget, cash_outflow=budget)


def _build_acquisition_impact(context: DecisionContext) -> ActionImpact:
    cash_cost = float(getattr(context.action, "cash_cost"))
    return ActionImpact(initiative_budget=cash_cost, cash_outflow=cash_cost)


def _build_one_time_spend_impact(context: DecisionContext) -> ActionImpact:
    cash_cost = float(getattr(context.action, "cash_cost"))
    return ActionImpact(initiative_budget=cash_cost, cash_outflow=cash_cost)


def _build_capex_impact(context: DecisionContext) -> ActionImpact:
    cost = float(getattr(context.action, "cost"))
    return ActionImpact(initiative_budget=cost, cash_outflow=cost)


def _build_launch_sku_impact(context: DecisionContext) -> ActionImpact:
    launch_cost = float(getattr(context.action, "launch_cost"))
    return ActionImpact(initiative_budget=launch_cost, cash_outflow=launch_cost)


def _build_retention_program_impact(context: DecisionContext) -> ActionImpact:
    cost = float(getattr(context.action, "cost"))
    return ActionImpact(initiative_budget=cost, cash_outflow=cost)


def _build_supplier_renegotiation_impact(context: DecisionContext) -> ActionImpact:
    cost = float(getattr(context.action, "cost"))
    return ActionImpact(initiative_budget=cost, cash_outflow=cost)


def _build_price_change_impact(context: DecisionContext) -> ActionImpact:
    _ = context
    return ActionImpact(initiative_budget=0.0, cash_outflow=0.0)


def _build_accept_order_impact(context: DecisionContext) -> ActionImpact:
    _ = context
    return ActionImpact(initiative_budget=0.0, cash_outflow=0.0)


def _build_marketing_increase_impact(context: DecisionContext) -> ActionImpact:
    added_monthly_spend = float(getattr(context.action, "added_monthly_spend"))
    return ActionImpact(
        initiative_budget=added_monthly_spend,
        cash_outflow=0.0,
        monthly_burn_delta=added_monthly_spend,
    )


def _build_discontinue_line_impact(context: DecisionContext) -> ActionImpact:
    _ = context
    return ActionImpact(initiative_budget=0.0, cash_outflow=0.0)


_ACTION_IMPACT_BUILDERS: dict[str, Callable[[DecisionContext], ActionImpact]] = {
    "hire": _build_hire_impact,
    "channel_test": _build_channel_test_impact,
    "acquisition": _build_acquisition_impact,
    "one_time_spend": _build_one_time_spend_impact,
    "price_change": _build_price_change_impact,
    "accept_order": _build_accept_order_impact,
    "capex_expansion": _build_capex_impact,
    "launch_sku": _build_launch_sku_impact,
    "marketing_increase": _build_marketing_increase_impact,
    "discontinue_line": _build_discontinue_line_impact,
    "retention_program": _build_retention_program_impact,
    "supplier_renegotiation": _build_supplier_renegotiation_impact,
}


def _get_numeric_fact(context: DecisionContext, fact_name: str) -> float:
    fact = context.company.facts[fact_name]
    return float(fact.value)


def _extract_threshold(pattern: re.Pattern[str], expression: str) -> float:
    match = pattern.search(" ".join(expression.split()))
    if match is None:
        raise ValueError(f"Unsupported constraint expression: {expression}")
    return float(match.group(1))


def _extract_capacity_backlog_terms(expression: str) -> tuple[int, float]:
    match = _CAPACITY_BACKLOG_PATTERN.search(" ".join(expression.split()))
    if match is None:
        raise ValueError(f"Unsupported constraint expression: {expression}")
    return int(float(match.group(1))), float(match.group(2))


def _get_text_fact(context: DecisionContext, fact_name: str) -> str:
    fact = context.company.facts[fact_name]
    value = fact.value
    if not isinstance(value, str):
        raise TypeError(f"Expected text fact for {fact_name}, got {type(value).__name__}")
    return value


def _classify_constraint(expression: str) -> ConstraintFamily:
    normalized = " ".join(expression.split())
    if normalized.startswith("cash_balance(t) >="):
        return _CASH_RESERVE_FLOOR
    if normalized.startswith("runway_months(t) = cash_balance(t)/net_burn(t) >="):
        return _RUNWAY_FLOOR
    if normalized.startswith("initiative_budget <="):
        return _INITIATIVE_BUDGET
    if normalized.startswith("ltv_cac(channel) >="):
        return _LTV_CAC_MINIMUM
    if normalized.startswith("cumulative_units_built("):
        return _CAPACITY_BACKLOG
    if normalized.startswith("new_sku_contribution_margin >="):
        return _NEW_SKU_MARGIN
    if normalized.startswith("total_marketing_spend <="):
        return _MARKETING_SPEND_CAP
    return "unknown"


def _constraint_applies(family: ConstraintFamily, action_type: str) -> bool:
    if family in {_CASH_RESERVE_FLOOR, _RUNWAY_FLOOR, _INITIATIVE_BUDGET}:
        return True
    if family == _LTV_CAC_MINIMUM:
        return action_type == "channel_test"
    if family == _CAPACITY_BACKLOG:
        return action_type in {"accept_order", "capex_expansion"}
    if family == _NEW_SKU_MARGIN:
        return action_type == "launch_sku"
    if family == _MARKETING_SPEND_CAP:
        return action_type == "marketing_increase"
    return True
