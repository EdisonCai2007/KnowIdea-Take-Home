from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from ..contracts.battery import StatedAssumption
from ..contracts.output import (
    BindingConstraintResult,
    Classification,
    DerivationStep,
    RefutationResult,
    Stage1ReadyOutcome,
    Stage2ProofComparison,
    Stage2ProofComputation,
    Stage2ProofDraft,
    Stage2ProofOperand,
    Stage2ProofPremise,
    Stage2ProofValidationIssue,
    Stage2ProofValidationReport,
    VerificationResult,
)

_FLOAT_TOLERANCE = 1e-6
_NUMBER_PATTERN = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?%?")


@dataclass(slots=True)
class _ValidationState:
    ready_result: Stage1ReadyOutcome
    answers: dict[str, str]
    issues: list[Stage2ProofValidationIssue] = field(default_factory=list)
    checked_premise_ids: list[str] = field(default_factory=list)
    checked_computation_ids: list[str] = field(default_factory=list)
    checked_comparison_ids: list[str] = field(default_factory=list)
    source_lookup: dict[str, str] = field(init=False)
    premise_lookup: dict[str, Stage2ProofPremise] = field(init=False)
    computation_lookup: dict[str, Stage2ProofComputation] = field(init=False)
    comparison_lookup: dict[str, Stage2ProofComparison] = field(init=False)
    premise_values: dict[str, int | float | None] = field(default_factory=dict)
    computation_values: dict[str, int | float | None] = field(default_factory=dict)
    comparison_results: dict[str, bool] = field(default_factory=dict)
    _issue_keys: set[tuple[str, str | None, str]] = field(default_factory=set)
    _computation_stack: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.source_lookup = _build_source_lookup(self.ready_result, self.answers)
        self.premise_lookup = {}
        self.computation_lookup = {}
        self.comparison_lookup = {}

    def add_issue(self, code: str, message: str, subject_id: str | None = None) -> None:
        key = (code, subject_id, message)
        if key in self._issue_keys:
            return
        self._issue_keys.add(key)
        self.issues.append(
            Stage2ProofValidationIssue(code=code, message=message, subject_id=subject_id)
        )


def validate_stage2_proof_draft(
    proof_draft: Stage2ProofDraft,
    *,
    ready_result: Stage1ReadyOutcome,
    answers: dict[str, str],
) -> Stage2ProofValidationReport:
    state = _ValidationState(ready_result=ready_result, answers=answers)
    _validate_ids(proof_draft, state)
    _validate_premises(proof_draft.premises, state)
    if (
        proof_draft.proposed_verdict != Classification.UNDECIDABLE
        and not proof_draft.comparisons
    ):
        state.add_issue(
            "load_bearing_gap",
            "Decisive proof drafts must include at least one executable comparison.",
        )

    for computation in proof_draft.computations:
        _resolve_computation(computation.id, state)

    for comparison in proof_draft.comparisons:
        _evaluate_comparison(comparison, state)

    blocking_codes = {
        "duplicate_id",
        "unsupported_operation",
        "invalid_operand_type",
        "division_by_zero",
        "result_mismatch",
        "load_bearing_gap",
        "unknown_reference",
    }
    blocking_issues = [issue for issue in state.issues if issue.code in blocking_codes]
    failed_comparisons = [issue for issue in state.issues if issue.code == "comparison_failed"]

    if blocking_issues or not state.checked_comparison_ids:
        final_classification = Classification.UNDECIDABLE
        accepted = False
    elif failed_comparisons:
        final_classification = Classification.REFUTED
        accepted = True
    else:
        final_classification = Classification.SUPPORTED
        accepted = True

    return Stage2ProofValidationReport(
        accepted=accepted,
        issues=state.issues,
        checked_premise_ids=state.checked_premise_ids,
        checked_computation_ids=state.checked_computation_ids,
        checked_comparison_ids=state.checked_comparison_ids,
        final_classification=final_classification,
        downgraded_from_model_verdict=final_classification != proof_draft.proposed_verdict,
    )


def build_proof_verification_result(
    proof_draft: Stage2ProofDraft,
    validation_report: Stage2ProofValidationReport,
) -> VerificationResult:
    authoritative_classification = proof_draft.proposed_verdict
    derivation: list[DerivationStep] = []
    computation_lookup = {item.id: item for item in proof_draft.computations}
    comparison_lookup = {item.id: item for item in proof_draft.comparisons}

    for premise_id in validation_report.checked_premise_ids:
        premise = next((item for item in proof_draft.premises if item.id == premise_id), None)
        if premise is None:
            continue
        derivation.append(
            DerivationStep(
                rule="stage2_accept_premise",
                inputs={"premise_id": premise.id, "kind": premise.kind, "source_locator": premise.source_locator},
                result=premise.statement,
            )
        )

    for computation_id in validation_report.checked_computation_ids:
        computation = computation_lookup.get(computation_id)
        if computation is None:
            continue
        derivation.append(
            DerivationStep(
                rule="stage2_compute",
                inputs={
                    "computation_id": computation.id,
                    "op": computation.op,
                    "args": [_serialize_operand(item) for item in computation.args],
                },
                result=computation.result,
            )
        )

    binding_constraints: list[BindingConstraintResult] = []
    comparison_failed_ids = {
        issue.subject_id
        for issue in validation_report.issues
        if issue.code == "comparison_failed" and issue.subject_id
    }
    for comparison_id in validation_report.checked_comparison_ids:
        comparison = comparison_lookup.get(comparison_id)
        if comparison is None:
            continue
        passed = comparison_id not in comparison_failed_ids
        derivation.append(
            DerivationStep(
                rule="stage2_compare",
                inputs={
                    "comparison_id": comparison.id,
                    "lhs": _serialize_operand(comparison.lhs),
                    "operator": comparison.operator,
                    "rhs": _serialize_operand(comparison.rhs),
                },
                result={"passed": passed},
            )
        )
        binding_constraints.append(
            BindingConstraintResult(
                id=comparison.id,
                passed=passed,
                why=(
                    "The validated comparison passed."
                    if passed
                    else "The validated comparison failed."
                ),
            )
        )

    load_bearing_assumptions = [
        StatedAssumption(id=premise.id, statement=premise.statement, status="given")
        for premise in proof_draft.premises
        if premise.kind == "assumption" and premise.id in validation_report.checked_premise_ids
    ]

    blocking_messages = [
        issue.message
        for issue in validation_report.issues
        if issue.code != "comparison_failed"
    ]
    comparison_failure_messages = [
        issue.message
        for issue in validation_report.issues
        if issue.code == "comparison_failed"
    ]

    if authoritative_classification == Classification.SUPPORTED:
        failure_conditions = None
    elif authoritative_classification == Classification.REFUTED:
        failure_conditions = "; ".join(comparison_failure_messages) or proof_draft.refutation_attempt
    else:
        failure_conditions = "; ".join(blocking_messages) or "The proof draft could not be validated end to end."

    pivotal_assumption = None
    if authoritative_classification == Classification.UNDECIDABLE:
        pivotal_assumption = blocking_messages[0] if blocking_messages else None

    return VerificationResult(
        classification=authoritative_classification,
        derivation=derivation,
        binding_constraints=binding_constraints,
        load_bearing_assumptions=load_bearing_assumptions,
        refutation=RefutationResult(
            attempted=True,
            failure_conditions=failure_conditions,
        ),
        pivotal_assumption=pivotal_assumption,
        flip_threshold=None,
        supported_if=None,
        refuted_if=None,
    )


def _validate_ids(proof_draft: Stage2ProofDraft, state: _ValidationState) -> None:
    all_ids = [item.id for item in proof_draft.premises]
    all_ids.extend(item.id for item in proof_draft.computations)
    all_ids.extend(item.id for item in proof_draft.comparisons)

    duplicates = {item_id for item_id, count in Counter(all_ids).items() if count > 1}
    for duplicate_id in sorted(duplicates):
        state.add_issue("duplicate_id", f"Duplicate proof id '{duplicate_id}' is not allowed.", duplicate_id)

    state.premise_lookup = {item.id: item for item in proof_draft.premises}
    state.computation_lookup = {item.id: item for item in proof_draft.computations}
    state.comparison_lookup = {item.id: item for item in proof_draft.comparisons}


def _validate_premises(
    premises: list[Stage2ProofPremise],
    state: _ValidationState,
) -> None:
    for premise in premises:
        if premise.id in state.checked_premise_ids:
            continue
        state.checked_premise_ids.append(premise.id)


def _resolve_computation(computation_id: str, state: _ValidationState) -> int | float | None:
    if computation_id in state.computation_values:
        return state.computation_values[computation_id]
    if computation_id in state._computation_stack:
        state.add_issue(
            "unknown_reference",
            f"Computation '{computation_id}' participates in a cyclic dependency.",
            computation_id,
        )
        state.computation_values[computation_id] = None
        return None

    computation = state.computation_lookup.get(computation_id)
    if computation is None:
        state.add_issue(
            "unknown_reference",
            f"Computation '{computation_id}' was referenced but not defined.",
            computation_id,
        )
        return None

    state._computation_stack.add(computation_id)
    arg_values: list[int | float] = []
    for operand in computation.args:
        value = _resolve_operand(operand, state, subject_id=computation.id)
        if value is None:
            state.computation_values[computation_id] = None
            state._computation_stack.discard(computation_id)
            return None
        arg_values.append(value)

    if computation.op == "add":
        resolved_result = sum(arg_values)
    elif computation.op == "sub":
        resolved_result = arg_values[0] - sum(arg_values[1:])
    elif computation.op == "mul":
        resolved_result = 1.0
        for value in arg_values:
            resolved_result *= value
    elif computation.op == "div":
        divisor = arg_values[1]
        if math.isclose(divisor, 0.0, abs_tol=_FLOAT_TOLERANCE):
            state.add_issue(
                "division_by_zero",
                f"Computation '{computation.id}' divides by zero.",
                computation.id,
            )
            state.computation_values[computation_id] = None
            state._computation_stack.discard(computation_id)
            return None
        resolved_result = arg_values[0]
        for value in arg_values[1:]:
            if math.isclose(value, 0.0, abs_tol=_FLOAT_TOLERANCE):
                state.add_issue(
                    "division_by_zero",
                    f"Computation '{computation.id}' divides by zero.",
                    computation.id,
                )
                state.computation_values[computation_id] = None
                state._computation_stack.discard(computation_id)
                return None
            resolved_result /= value
    else:
        state.add_issue(
            "unsupported_operation",
            f"Computation '{computation.id}' uses unsupported op '{computation.op}'.",
            computation.id,
        )
        state.computation_values[computation_id] = None
        state._computation_stack.discard(computation_id)
        return None

    if not _numeric_matches(resolved_result, computation.result):
        state.add_issue(
            "result_mismatch",
            f"Computation '{computation.id}' does not recompute to the model-provided result.",
            computation.id,
        )
        state.computation_values[computation_id] = None
        state._computation_stack.discard(computation_id)
        return None

    state.computation_values[computation_id] = resolved_result
    if computation.id not in state.checked_computation_ids:
        state.checked_computation_ids.append(computation.id)
    state._computation_stack.discard(computation_id)
    return resolved_result


def _evaluate_comparison(
    comparison: Stage2ProofComparison,
    state: _ValidationState,
) -> bool | None:
    lhs = _resolve_operand(comparison.lhs, state, subject_id=comparison.id)
    rhs = _resolve_operand(comparison.rhs, state, subject_id=comparison.id)
    if lhs is None or rhs is None:
        state.add_issue(
            "load_bearing_gap",
            f"Comparison '{comparison.id}' could not be evaluated because one or more operands are unresolved.",
            comparison.id,
        )
        return None

    if comparison.operator == "<":
        passed = lhs < rhs
    elif comparison.operator == "<=":
        passed = lhs <= rhs
    elif comparison.operator == ">":
        passed = lhs > rhs
    elif comparison.operator == ">=":
        passed = lhs >= rhs
    elif comparison.operator == "==":
        passed = _numeric_matches(lhs, rhs)
    else:
        state.add_issue(
            "unsupported_operation",
            f"Comparison '{comparison.id}' uses unsupported operator '{comparison.operator}'.",
            comparison.id,
        )
        return None

    state.comparison_results[comparison.id] = passed
    if comparison.id not in state.checked_comparison_ids:
        state.checked_comparison_ids.append(comparison.id)
    if not passed:
        state.add_issue(
            "comparison_failed",
            f"Comparison '{comparison.id}' evaluated to false.",
            comparison.id,
        )
    return passed


def _resolve_operand(
    operand: Stage2ProofOperand,
    state: _ValidationState,
    *,
    subject_id: str,
) -> int | float | None:
    if operand.kind == "literal":
        return operand.value

    ref_id = operand.value
    if ref_id in state.premise_lookup:
        return _resolve_premise_value(ref_id, state)
    if ref_id in state.computation_lookup:
        return _resolve_computation(ref_id, state)

    state.add_issue(
        "unknown_reference",
        f"Proof step '{subject_id}' references unknown id '{ref_id}'.",
        subject_id,
    )
    return None


def _resolve_premise_value(premise_id: str, state: _ValidationState) -> int | float | None:
    if premise_id in state.premise_values:
        return state.premise_values[premise_id]

    premise = state.premise_lookup[premise_id]
    source_quote = state.source_lookup.get(premise.source_locator, premise.statement)
    extracted_value = _extract_numeric_value(premise.statement)
    if extracted_value is None:
        extracted_value = _extract_numeric_value(source_quote)
    if extracted_value is None:
        state.add_issue(
            "invalid_operand_type",
            f"Premise '{premise.id}' does not expose exactly one numeric value that code can evaluate.",
            premise.id,
        )
        state.premise_values[premise_id] = None
        return None

    state.premise_values[premise_id] = extracted_value
    return extracted_value


def _build_source_lookup(
    ready_result: Stage1ReadyOutcome,
    answers: dict[str, str],
) -> dict[str, str]:
    context = ready_result.working_context
    lookup = {
        "proposal_text": ready_result.proposal,
        "working_context.decision": context.decision,
        "working_context.objective": context.objective,
    }
    lookup.update(
        {
            f"working_context.what_we_know[{index}]": value
            for index, value in enumerate(context.what_we_know)
        }
    )
    lookup.update(
        {
            f"working_context.constraints_mentioned[{index}]": value
            for index, value in enumerate(context.constraints_mentioned)
        }
    )
    lookup.update(
        {
            f"working_context.success_criteria[{index}]": value
            for index, value in enumerate(context.success_criteria)
        }
    )
    lookup.update(
        {
            f"working_context.what_still_matters[{index}]": value
            for index, value in enumerate(context.what_still_matters)
        }
    )
    lookup.update(
        {
            f"unresolved_notes[{index}]": value
            for index, value in enumerate(ready_result.unresolved_notes)
        }
    )
    lookup.update(
        {
            f"transcript[{index}]": turn.text
            for index, turn in enumerate(ready_result.transcript)
        }
    )
    lookup.update({f"answer.{question_id}": answer for question_id, answer in answers.items()})
    return lookup


def _extract_numeric_value(text: str) -> int | float | None:
    matches = _NUMBER_PATTERN.findall(text)
    if len(matches) != 1:
        return None

    raw_match = matches[0].replace(",", "")
    percent = raw_match.endswith("%")
    raw_value = raw_match.rstrip("%").lstrip("$€£")
    try:
        numeric = float(raw_value)
    except ValueError:
        return None

    if percent:
        numeric /= 100.0
    if float(numeric).is_integer():
        return int(numeric)
    return numeric


def _numeric_matches(left: int | float, right: int | float) -> bool:
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    return math.isclose(float(left), float(right), abs_tol=_FLOAT_TOLERANCE)


def _serialize_operand(operand: Stage2ProofOperand) -> dict[str, int | float | str]:
    return {"kind": operand.kind, "value": operand.value}
