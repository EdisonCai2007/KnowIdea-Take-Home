from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.battery import StatedAssumption
from ..contracts.context import DecisionContext
from ..contracts.output import (
    BindingConstraintResult,
    Classification,
    DerivationStep,
    RefutationResult,
    VerificationResult,
)


def normalize_number(value: float) -> int | float:
    rounded = round(float(value), 4)
    if rounded.is_integer():
        return int(rounded)
    return rounded


@dataclass(slots=True)
class ActionImpact:
    initiative_budget: float
    cash_outflow: float
    monthly_burn_delta: float = 0.0

    def as_json(self) -> dict[str, int | float]:
        return {
            "initiative_budget": normalize_number(self.initiative_budget),
            "cash_outflow": normalize_number(self.cash_outflow),
            "monthly_burn_delta": normalize_number(self.monthly_burn_delta),
        }


@dataclass(slots=True)
class VerificationSession:
    context: DecisionContext
    derivation: list[DerivationStep] = field(default_factory=list)
    binding_constraints: list[BindingConstraintResult] = field(default_factory=list)
    load_bearing_assumptions: list[StatedAssumption] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    _assumption_lookup: dict[str, StatedAssumption] = field(init=False)
    _added_assumptions: set[str] = field(default_factory=set, init=False)
    _action_impact: ActionImpact | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._assumption_lookup = {
            assumption.id: assumption for assumption in self.context.stated_assumptions
        }

    @property
    def action_impact(self) -> ActionImpact | None:
        return self._action_impact

    def store_action_impact(self, impact: ActionImpact) -> ActionImpact:
        if self._action_impact is None:
            self._action_impact = impact
            self.add_step(
                "compute_action_impact",
                {"action_type": self.context.action.type},
                impact.as_json(),
            )
        return self._action_impact

    def add_step(self, rule: str, inputs: dict[str, Any], result: Any) -> None:
        self.derivation.append(DerivationStep(rule=rule, inputs=inputs, result=result))

    def add_binding_constraint(self, constraint_id: str, passed: bool, why: str) -> None:
        self.binding_constraints.append(
            BindingConstraintResult(id=constraint_id, passed=passed, why=why)
        )

    def add_assumption(self, assumption_id: str) -> None:
        if assumption_id in self._added_assumptions:
            return

        assumption = self._assumption_lookup.get(assumption_id)
        if assumption is None:
            return

        self._added_assumptions.add(assumption_id)
        self.load_bearing_assumptions.append(assumption)

    def add_projected_assumptions(self) -> None:
        for assumption in self.context.stated_assumptions:
            if assumption.status == "projected":
                self.add_assumption(assumption.id)

    def binding_constraint_passed(self, constraint_id: str) -> bool:
        return any(
            binding.id == constraint_id and binding.passed for binding in self.binding_constraints
        )

    def coverage_gap_result(
        self,
        *,
        stage: str,
        reason: str,
        inputs: dict[str, Any] | None = None,
    ) -> VerificationResult:
        self.coverage_gaps.append(reason)
        payload = {"stage": stage}
        if inputs:
            payload.update(inputs)
        self.add_step("coverage_gap", payload, reason)
        return self.undecidable_result(
            pivotal_assumption="Verifier rule coverage is incomplete for this decision shape.",
            flip_threshold="The verdict boundary cannot be computed until the missing verifier rule exists.",
            supported_if="the missing verifier rule is implemented and the checked derivation succeeds",
            refuted_if="the missing verifier rule is implemented and the checked derivation fails",
            failure_conditions=reason,
        )

    def refuted_result(self, *, failure_conditions: str) -> VerificationResult:
        return self._build_result(
            classification=Classification.REFUTED,
            failure_conditions=failure_conditions,
        )

    def supported_result(self) -> VerificationResult:
        return self._build_result(
            classification=Classification.SUPPORTED,
            failure_conditions=None,
        )

    def undecidable_result(
        self,
        *,
        pivotal_assumption: str,
        flip_threshold: Any,
        supported_if: str,
        refuted_if: str,
        failure_conditions: str | None,
    ) -> VerificationResult:
        return self._build_result(
            classification=Classification.UNDECIDABLE,
            failure_conditions=failure_conditions,
            pivotal_assumption=pivotal_assumption,
            flip_threshold=flip_threshold,
            supported_if=supported_if,
            refuted_if=refuted_if,
        )

    def _build_result(
        self,
        *,
        classification: Classification,
        failure_conditions: str | None,
        pivotal_assumption: str | None = None,
        flip_threshold: Any | None = None,
        supported_if: str | None = None,
        refuted_if: str | None = None,
    ) -> VerificationResult:
        return VerificationResult(
            classification=classification,
            derivation=self.derivation,
            binding_constraints=self.binding_constraints,
            load_bearing_assumptions=self.load_bearing_assumptions,
            refutation=RefutationResult(
                attempted=True,
                failure_conditions=failure_conditions,
            ),
            pivotal_assumption=pivotal_assumption,
            flip_threshold=flip_threshold,
            supported_if=supported_if,
            refuted_if=refuted_if,
        )
