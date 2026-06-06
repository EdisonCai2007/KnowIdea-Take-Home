from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..contracts.output import (
    Classification,
    Stage1ReadyOutcome,
    Stage2FormalizationSuccess,
    Stage2ProofComparison,
    Stage2ProofComputation,
    Stage2ProofDraft,
)
from ..contracts.workspace import WorkspaceCompanyProfile
from ..runtime_logging import log_event
from ..settings import (
    ConfigurationError,
    DEFAULT_OPENROUTER_STAGE2_MODEL,
    OpenRouterSettings,
    get_openrouter_settings,
)
from ..verifier.proof_draft import validate_stage2_proof_draft
from .client import OpenRouterClient, OpenRouterCompletion, OpenRouterError


class WorkspaceFormalizationExecutionError(RuntimeError):
    """Raised when the Stage 2 formalizer cannot produce a usable result."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProofDraftModelOutput(StrictModel):
    proof_draft: Stage2ProofDraft
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FormalizerModelResult:
    output: ProofDraftModelOutput
    completion: OpenRouterCompletion


_NUMBER_PATTERN = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?%?")


SYSTEM_PROMPT = """You are the Stage 2 proof-draft AI in a business-decision verification workflow.
Return JSON only. Do not wrap it in markdown.

Your job is to turn a Stage 1 ready brief into a proof draft that code can validate.

Return:
- one claim
- premises that support an executable proof path
- AST-style computations only
- executable comparisons only
- one proposed verdict
- one refutation attempt
- unresolved gaps when important proof material is still missing

Rules:
- Do NOT emit battery JSON.
- Do NOT emit normalized bundles or grounding reports.
- Do NOT emit free-form formulas.
- Do NOT emit custom operation names.
- Do NOT emit custom locator namespaces.
- Use only these computation ops: add, sub, mul, div.
- Use only these comparison operators: <, <=, >, >=, ==.
- Use only operand shapes:
  - {"kind":"ref","value":"<premise-or-computation-id>"}
  - {"kind":"literal","value":<number>}
- Every premise must include exactly one source_locator from the supplied allowed locator set for traceability.
- Code will evaluate premise statements directly, so phrase them in the clearest executable form.
- Prefer staying faithful to the supplied Stage 1 material, but optimize for a coherent proof draft over close paraphrase.
- Treat user-supplied estimates, projections, and future-looking numeric answers as fixed proof inputs.
- Do not add unresolved gaps merely because a provided number is estimated, projected, or about the future.
- Prefer a decisive verdict whenever one executable arithmetic path exists from the available numbers.
- Treat working_context.success_criteria as usable proof targets by default unless they directly conflict with other available material.
- Prefer the shortest executable proof path over fuller business context.
- If a proposal states a projected revenue or output increase and no explicit offset, cannibalization, or countervailing effect is available, you may treat that projection as additive for the purpose of the proof draft.
- Do not require auxiliary business context such as staffing, timeline, demographics, or operational details unless the chosen arithmetic path actually depends on them.
- Use unresolved_gaps only when a number or condition required by your chosen proof path is truly missing.
- If the available numbers let you compute the target comparison, return SUPPORTED or REFUTED rather than UNDECIDABLE.
- If you return SUPPORTED or REFUTED, you must include at least one executable comparison.
- Include computations whenever the comparison depends on a derived quantity.
- Do not return a decisive verdict with only premises and prose.
- Be extremely careful with premise references inside computations.
- Every computation result must be derivable from exactly the listed args and nothing else.
- Do not let a computation result implicitly depend on a premise id that is not present in that computation's args.
- If a result requires current revenue, new revenue, and existing-location impact, include all three referenced inputs explicitly.
- Never use a premise id as shorthand for a larger quantity than the premise statement actually says.
- Prefer fewer numeric premises with clearer roles over many overlapping premises.
- If a numeric fact is available both in what_we_know and in an answer, prefer the answer.<question_id> locator for the numeric premise.
- Before returning, silently recompute every computation from its args, then verify every comparison from those recomputed values.
- If any computation result does not match the listed args exactly, rewrite the args or result before returning.
- Proposed verdict must be one of: SUPPORTED, REFUTED, UNDECIDABLE.
"""

REPAIR_SYSTEM_PROMPT = """You previously returned a Stage 2 proof draft that did not provide a usable executable proof structure.
Return JSON only. Do not wrap it in markdown.

Repair the proof draft so code can execute it.

Rules:
- If you return SUPPORTED or REFUTED, include at least one executable comparison.
- Include computations whenever a comparison depends on a derived value.
- Do not return only premises and a verdict.
- Populate the executable proof structure directly inside proof_draft.computations and proof_draft.comparisons.
- Do not put the AST only in notes, prose, reasoning, fenced code blocks, or any field outside proof_draft.
- Keep source_locators valid and use only the allowed ops/operators.
- Use only these operand JSON shapes everywhere in computations and comparisons:
  - {"kind":"ref","value":"<premise-or-computation-id>"}
  - {"kind":"literal","value":<number>}
- Do not invent custom operand kinds such as premise_value, computation_result, constant, premise, computed, or similar variants.
- When referencing a premise or computation, always use {"kind":"ref","value":"the_id"}.
- When referencing a numeric constant such as 0.4 or 100, always use {"kind":"literal","value":0.4} or {"kind":"literal","value":100}.
- Use only these computation ops: add, sub, mul, div.
- Use only these comparison operators: <, <=, >, >=, ==.
- If no executable comparison can be built from the available material, change the verdict to UNDECIDABLE and explain the missing proof material in unresolved_gaps.
- Before returning, silently recompute every computation and verify every comparison.
"""


def generate_workspace_formalization(
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
    ready_result: Stage1ReadyOutcome,
    answers: dict[str, str],
    settings: OpenRouterSettings | None = None,
    client: Any | None = None,
) -> Stage2FormalizationSuccess:
    settings, resolved_client = _resolve_client(settings=settings, client=client)
    payload = _build_formalization_payload(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        ready_result=ready_result,
        answers=answers,
    )

    log_event(
        settings=settings,
        event="formalization.start",
        payload={"proposal_id": proposal_id},
        console_message=f"formalization.start proposal_id={proposal_id}",
    )

    model_result = _call_formalizer_model(client=resolved_client, payload=payload)
    output = _normalize_decisive_proof_draft(model_result.output)
    validation_report = validate_stage2_proof_draft(
        output.proof_draft,
        ready_result=ready_result,
        answers=answers,
    )
    repair_notes: list[str] = []
    if _should_retry_for_executable_proof(output.proof_draft, validation_report):
        log_event(
            settings=settings,
            event="formalization.retry",
            payload={
                "proposal_id": proposal_id,
                "reason": "decisive verdict without executable proof structure",
                "model_verdict": output.proof_draft.proposed_verdict.value,
                "checked_classification": validation_report.final_classification.value,
            },
            console_message=f"formalization.retry proposal_id={proposal_id}",
        )
        try:
            model_result = _call_formalizer_model(
                client=resolved_client,
                payload=payload,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                repair_context={
                    "reason": "The previous draft did not contain an executable proof path.",
                    "previous_proof_draft": output.proof_draft.model_dump(mode="json"),
                    "previous_validation_report": validation_report.model_dump(mode="json"),
                },
            )
            output = _normalize_decisive_proof_draft(model_result.output)
            salvaged_output = _maybe_salvage_executable_proof(
                output=output,
                completion=model_result.completion,
            )
            if salvaged_output is not None:
                output = _normalize_decisive_proof_draft(salvaged_output)
                repair_notes.append(
                    "Stage 2 salvage: recovered executable proof structure from the same model response."
                )
            repair_notes.append("Stage 2 retry: requested an explicit executable proof structure.")
        except WorkspaceFormalizationExecutionError:
            repair_notes.append(
                "Stage 2 retry: attempted to repair the proof draft into executable AST form, but the retry did not return usable JSON."
            )

    synthesized_output = _maybe_synthesize_executable_proof(output)
    if synthesized_output is not None:
        output = _normalize_decisive_proof_draft(synthesized_output)
        repair_notes.append(
            "Stage 2 fallback: synthesized executable proof structure from parsed premises."
        )

    validation_report = validate_stage2_proof_draft(
        output.proof_draft,
        ready_result=ready_result,
        answers=answers,
    )
    if validation_report.accepted:
        notes = _merge_notes(repair_notes, _build_validation_notes(validation_report))
    else:
        notes = _merge_notes(
            repair_notes,
            output.notes,
            output.proof_draft.unresolved_gaps,
            _build_validation_notes(validation_report),
        )
    result = Stage2FormalizationSuccess(
        status="formalized",
        proof_draft=output.proof_draft,
        validation_report=validation_report,
        notes=notes,
    )
    log_event(
        settings=settings,
        event="formalization.result",
        payload={
            "proposal_id": proposal_id,
            "status": result.status,
            "final_classification": result.validation_report.final_classification.value,
            "checked_classification": result.validation_report.final_classification.value,
            "model_verdict": result.proof_draft.proposed_verdict.value,
            "accepted": result.validation_report.accepted,
            "issue_count": len(result.validation_report.issues),
            "proof_draft": result.proof_draft.model_dump(mode="json"),
        },
        console_message=(
            f"formalization.result proposal_id={proposal_id} "
            f"status={result.status} classification={result.validation_report.final_classification.value}"
        ),
    )
    return result


def _build_formalization_payload(
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
    ready_result: Stage1ReadyOutcome,
    answers: dict[str, str],
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "proposal_text": _normalize_fixed_input_text(proposal_text),
        "workspace_company": {
            "name": workspace_company.name,
            "sector": workspace_company.sector,
        },
        "decision_kernel": _sanitize_fixed_input_payload(_build_decision_kernel(ready_result)),
        "answers": [
            {"question_id": question_id, "answer": answer}
            for question_id, answer in sorted(answers.items())
        ],
        "allowed_source_locators": _build_allowed_source_locators(ready_result, answers),
        "allowed_computation_ops": ["add", "sub", "mul", "div"],
        "allowed_comparison_operators": ["<", "<=", ">", ">=", "=="],
    }


def _build_decision_kernel(ready_result: Stage1ReadyOutcome) -> dict[str, Any]:
    context = ready_result.working_context
    return {
        "decision": context.decision,
        "objective": context.objective,
        "what_we_know": context.what_we_know,
        "constraints_mentioned": context.constraints_mentioned,
        "success_criteria": context.success_criteria,
        "what_still_matters": context.what_still_matters,
        "unresolved_notes": ready_result.unresolved_notes,
        "transcript": [
            {
                "speaker": turn.speaker,
                "kind": turn.kind,
                "text": turn.text,
                "question_id": turn.question_id,
            }
            for turn in ready_result.transcript
        ],
    }


def _build_allowed_source_locators(
    ready_result: Stage1ReadyOutcome,
    answers: dict[str, str],
) -> list[str]:
    context = ready_result.working_context
    locators = [
        "proposal_text",
        "working_context.decision",
        "working_context.objective",
    ]
    locators.extend(
        f"working_context.what_we_know[{index}]"
        for index, _value in enumerate(context.what_we_know)
    )
    locators.extend(
        f"working_context.constraints_mentioned[{index}]"
        for index, _value in enumerate(context.constraints_mentioned)
    )
    locators.extend(
        f"working_context.success_criteria[{index}]"
        for index, _value in enumerate(context.success_criteria)
    )
    locators.extend(
        f"working_context.what_still_matters[{index}]"
        for index, _value in enumerate(context.what_still_matters)
    )
    locators.extend(
        f"unresolved_notes[{index}]"
        for index, _value in enumerate(ready_result.unresolved_notes)
    )
    locators.extend(
        f"transcript[{index}]"
        for index, _value in enumerate(ready_result.transcript)
    )
    locators.extend(f"answer.{question_id}" for question_id in sorted(answers))
    return locators


def _resolve_client(
    *,
    settings: OpenRouterSettings | None,
    client: Any | None,
) -> tuple[OpenRouterSettings, Any]:
    if client is not None:
        resolved_settings = settings or get_openrouter_settings(
            require_api_key=False,
            model_env_var="OPENROUTER_STAGE2_MODEL",
            default_model=DEFAULT_OPENROUTER_STAGE2_MODEL,
        )
        return resolved_settings, client

    resolved_settings = settings or get_openrouter_settings(
        require_api_key=False,
        model_env_var="OPENROUTER_STAGE2_MODEL",
        default_model=DEFAULT_OPENROUTER_STAGE2_MODEL,
    )
    if resolved_settings.api_key is None:
        raise ConfigurationError(
            "OPENROUTER_API_KEY is required for Stage 2 formalization AI. Add it to .env or"
            " the process environment."
        )
    return resolved_settings, OpenRouterClient(resolved_settings)


def _call_formalizer_model(
    *,
    client: Any,
    payload: dict[str, Any],
    system_prompt: str = SYSTEM_PROMPT,
    repair_context: dict[str, Any] | None = None,
) -> FormalizerModelResult:
    request_payload = payload
    if repair_context is not None:
        request_payload = {
            "original_request": payload,
            "repair_context": repair_context,
        }
    try:
        completion = client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(request_payload, indent=2, sort_keys=True)},
            ],
            response_format=_build_response_format(),
        )
    except OpenRouterError as exc:
        raise WorkspaceFormalizationExecutionError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        if exc.__class__.__name__ == "OpenRouterError":
            raise WorkspaceFormalizationExecutionError(str(exc)) from exc
        raise

    try:
        output = ProofDraftModelOutput.model_validate_json(completion.raw_model_response)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid JSON"
        raise WorkspaceFormalizationExecutionError(
            f"OpenRouter returned invalid Stage 2 proof draft JSON: {error_message}."
        ) from exc
    return FormalizerModelResult(output=output, completion=completion)


def _build_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "decision_prover_stage2_proof_draft",
            "strict": True,
            "schema": ProofDraftModelOutput.model_json_schema(),
        },
    }


def _build_validation_notes(validation_report) -> list[str]:
    return [issue.message for issue in validation_report.issues]


def _should_retry_for_executable_proof(
    proof_draft: Stage2ProofDraft,
    validation_report,
) -> bool:
    if proof_draft.proposed_verdict == Classification.UNDECIDABLE:
        return False
    if proof_draft.comparisons:
        return False
    return validation_report.final_classification == Classification.UNDECIDABLE


def _normalize_decisive_proof_draft(output: ProofDraftModelOutput) -> ProofDraftModelOutput:
    proof_draft = output.proof_draft
    if proof_draft.proposed_verdict == Classification.UNDECIDABLE:
        return output

    premises = [
        premise.model_copy(update={"statement": _normalize_fixed_input_text(premise.statement)})
        for premise in proof_draft.premises
    ]
    unresolved_gaps = [
        gap for gap in proof_draft.unresolved_gaps if not _is_estimate_uncertainty_text(gap)
    ]
    refutation_attempt = _normalize_fixed_input_text(proof_draft.refutation_attempt)
    if _is_estimate_uncertainty_text(refutation_attempt):
        refutation_attempt = "No stronger refutation is available within the provided fixed inputs."

    normalized_draft = proof_draft.model_copy(
        update={
            "claim": _normalize_fixed_input_text(proof_draft.claim),
            "premises": premises,
            "refutation_attempt": refutation_attempt,
            "unresolved_gaps": unresolved_gaps,
        }
    )
    notes = [
        note for note in output.notes if not _is_estimate_uncertainty_text(note)
    ]
    return output.model_copy(update={"proof_draft": normalized_draft, "notes": notes})


def _maybe_salvage_executable_proof(
    *,
    output: ProofDraftModelOutput,
    completion: OpenRouterCompletion,
) -> ProofDraftModelOutput | None:
    proof_draft = output.proof_draft
    if proof_draft.proposed_verdict == Classification.UNDECIDABLE:
        return None
    if proof_draft.comparisons:
        return None

    salvaged_ast = _extract_salvage_ast(
        completion=completion,
        expected_verdict=proof_draft.proposed_verdict,
    )
    if salvaged_ast is None:
        return None

    repaired_draft = proof_draft.model_copy(
        update={
            "computations": salvaged_ast["computations"],
            "comparisons": salvaged_ast["comparisons"],
        }
    )
    return output.model_copy(update={"proof_draft": repaired_draft})


def _extract_salvage_ast(
    *,
    completion: OpenRouterCompletion,
    expected_verdict: Classification,
) -> dict[str, list[Stage2ProofComputation] | list[Stage2ProofComparison]] | None:
    for text in _iter_salvage_texts(completion):
        for candidate in _iter_json_candidates(text):
            salvaged_ast = _extract_ast_from_candidate(
                candidate=candidate,
                expected_verdict=expected_verdict,
            )
            if salvaged_ast is not None:
                return salvaged_ast
    return None


def _iter_salvage_texts(completion: OpenRouterCompletion) -> list[str]:
    texts: list[str] = []
    if completion.raw_model_response:
        texts.append(completion.raw_model_response)
    if completion.provider_response_json is not None:
        texts.extend(_collect_string_values(completion.provider_response_json))
    if completion.raw_provider_response:
        texts.append(completion.raw_provider_response)

    unique_texts: list[str] = []
    for text in texts:
        normalized = text.strip()
        if normalized and normalized not in unique_texts:
            unique_texts.append(normalized)
    return unique_texts


def _collect_string_values(value: Any) -> list[str]:
    collected: list[str] = []
    if isinstance(value, str):
        collected.append(value)
        return collected
    if isinstance(value, list):
        for item in value:
            collected.extend(_collect_string_values(item))
        return collected
    if isinstance(value, dict):
        for item in value.values():
            collected.extend(_collect_string_values(item))
    return collected


def _iter_json_candidates(text: str) -> list[Any]:
    candidates: list[Any] = []
    for block in _extract_fenced_json_blocks(text):
        parsed = _try_parse_candidate_json(block)
        if parsed is not None:
            candidates.append(parsed)

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _end = decoder.raw_decode(text[match.start() :])
        except ValueError:
            continue
        candidates.append(candidate)
    return candidates


def _extract_fenced_json_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
    return [match.group(1) for match in pattern.finditer(text)]


def _try_parse_candidate_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _extract_ast_from_candidate(
    *,
    candidate: Any,
    expected_verdict: Classification,
) -> dict[str, list[Stage2ProofComputation] | list[Stage2ProofComparison]] | None:
    for block in _iter_ast_blocks(candidate):
        verdict = block.get("verdict") or block.get("proposed_verdict")
        if verdict is not None and verdict != expected_verdict.value:
            continue

        computations = block.get("computations")
        comparisons = block.get("comparisons")
        if not isinstance(computations, list) or not isinstance(comparisons, list):
            continue
        if not computations and not comparisons:
            continue
        if not comparisons:
            continue

        try:
            parsed_computations = [
                Stage2ProofComputation.model_validate(item) for item in computations
            ]
            parsed_comparisons = [
                Stage2ProofComparison.model_validate(item) for item in comparisons
            ]
        except ValidationError:
            continue
        return {
            "computations": parsed_computations,
            "comparisons": parsed_comparisons,
        }
    return None


def _iter_ast_blocks(candidate: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if isinstance(candidate, dict):
        if "computations" in candidate and "comparisons" in candidate:
            blocks.append(candidate)
        for value in candidate.values():
            blocks.extend(_iter_ast_blocks(value))
    elif isinstance(candidate, list):
        for item in candidate:
            blocks.extend(_iter_ast_blocks(item))
    return blocks


def _maybe_synthesize_executable_proof(
    output: ProofDraftModelOutput,
) -> ProofDraftModelOutput | None:
    proof_draft = output.proof_draft
    if proof_draft.proposed_verdict == Classification.UNDECIDABLE:
        return None
    if proof_draft.comparisons:
        return None

    current_revenue = _find_numeric_premise(
        proof_draft,
        "current overall brand revenue",
        "current_revenue",
    )
    target_increase_pct = _find_numeric_premise(
        proof_draft,
        "increase overall brand revenue",
        "target_increase",
    )
    new_location_revenue = _find_numeric_premise(
        proof_draft,
        "new downtown location",
        "new_location_revenue",
    )
    revenue_impact = _find_numeric_premise(
        proof_draft,
        "impact on the existing location",
        "revenue_impact",
    )
    if current_revenue is None or target_increase_pct is None or new_location_revenue is None:
        return None

    current_id, current_value = current_revenue
    target_id, target_value = target_increase_pct
    new_revenue_id, new_revenue_value = new_location_revenue
    impact_id, impact_value = revenue_impact if revenue_impact is not None else (None, 0)

    target_amount = current_value * target_value
    target_computation = Stage2ProofComputation(
        id="synth_target_increase_amount",
        op="mul",
        args=[
            {"kind": "ref", "value": current_id},
            {"kind": "ref", "value": target_id},
        ],
        result=_coerce_numeric_result(target_amount),
    )

    actual_increase_operand = {"kind": "ref", "value": new_revenue_id}
    computations = [target_computation]
    if impact_id is not None:
        actual_increase = new_revenue_value + impact_value
        actual_increase_computation = Stage2ProofComputation(
            id="synth_projected_net_increase",
            op="add",
            args=[
                {"kind": "ref", "value": new_revenue_id},
                {"kind": "ref", "value": impact_id},
            ],
            result=_coerce_numeric_result(actual_increase),
        )
        computations.append(actual_increase_computation)
        actual_increase_operand = {"kind": "ref", "value": actual_increase_computation.id}

    comparison = Stage2ProofComparison(
        id="synth_revenue_increase_target",
        lhs=actual_increase_operand,
        operator=">=",
        rhs={"kind": "ref", "value": target_computation.id},
    )

    repaired_draft = proof_draft.model_copy(
        update={
            "computations": computations,
            "comparisons": [comparison],
        }
    )
    return output.model_copy(update={"proof_draft": repaired_draft})


def _find_numeric_premise(
    proof_draft: Stage2ProofDraft,
    required_phrase: str,
    id_hint: str,
) -> tuple[str, int | float] | None:
    required_phrase_lower = required_phrase.lower()
    id_hint_lower = id_hint.lower()
    for premise in proof_draft.premises:
        text = premise.statement.lower()
        if required_phrase_lower not in text and id_hint_lower not in premise.id.lower():
            continue
        value = _extract_numeric_value(premise.statement)
        if value is None:
            continue
        return premise.id, value
    return None


def _sanitize_fixed_input_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_fixed_input_text(value)
    if isinstance(value, list):
        return [_sanitize_fixed_input_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize_fixed_input_payload(item)
            for key, item in value.items()
        }
    return value


def _normalize_fixed_input_text(text: str) -> str:
    normalized = text
    replacements = [
        (r"\ban estimated\s+", ""),
        (r"\ba projected\s+", ""),
        (r"\bestimated\s+", ""),
        (r"\bprojected\s+", ""),
        (r"\bprojection\s+", ""),
        (r"\bfuture-looking\s+", ""),
    ]
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace(" .", ".").replace(" ,", ",")
    return normalized.strip()


def _is_estimate_uncertainty_text(text: str) -> bool:
    normalized = text.lower()
    patterns = [
        "might be optimistic",
        "may not be accurate",
        "actual revenue is lower",
        "relies on revenue estimates",
        "based on the provided estimates",
        "projected revenue",
        "zero-cannibalization estimate",
        "if the actual revenue is lower",
    ]
    return any(pattern in normalized for pattern in patterns)


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
    return _coerce_numeric_result(numeric)


def _coerce_numeric_result(value: int | float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return value


def _merge_notes(*note_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for note_group in note_groups:
        for note in note_group:
            normalized = note.strip()
            if not normalized or normalized in merged:
                continue
            merged.append(normalized)
    return merged
