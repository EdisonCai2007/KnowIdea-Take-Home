from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..constants import canonical_battery_metadata
from ..contracts.actions import ACTION_REGISTRY, JsonValue, validate_action_payload
from ..contracts.battery import CompanyFact, Constraint, DecisionBattery, StatedAssumption
from ..contracts.output import (
    GroundingEntry,
    GroundingReport,
    NormalizedAction,
    NormalizedAssumption,
    NormalizedFact,
    NormalizedFeasibilityBundle,
    NormalizedGatingCondition,
    Stage1ReadyOutcome,
    Stage2FormalizationSuccess,
)
from ..contracts.workspace import WorkspaceCompanyProfile
from ..runtime_logging import log_event
from ..settings import ConfigurationError, OpenRouterSettings, get_openrouter_settings
from ..stage1 import canonicalize_company_id
from .client import OpenRouterClient, OpenRouterError


class WorkspaceFormalizationExecutionError(RuntimeError):
    """Raised when the Stage 2 formalizer cannot produce a usable result."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormalizationModelOutput(StrictModel):
    normalized_bundle: NormalizedFeasibilityBundle
    grounding_report: GroundingReport
    notes: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are the Stage 2 formalization AI in a business-decision verification workflow.
Return JSON only. Do not wrap it in markdown.

Your job is to convert a Stage 1 decision kernel into a normalized feasibility bundle.
Code will assemble the final DecisionBattery shell automatically.

Proof target:
- Identify the concrete proposed action.
- Identify explicit go/no-go gating conditions.
- Identify measurable known facts relevant to those gates.
- Identify unresolved proof-critical unknowns or explicit assumptions.
- Do not judge overall business quality or broad strategic success.

Rules:
- Do NOT emit battery-level metadata fields.
- Do NOT emit company shell fields such as id, name, or sector.
- Do NOT emit decision shell fields such as id, company, proposal, or objective.
- Do NOT emit verifier outputs or verdicts.
- Use the provided Stage 1 decision kernel as the source of truth.
- Preserve Stage 1 statements verbatim when possible in `statement` fields.
- Prefer a sparse but faithful normalization over a complete-looking but fabricated one.
- Do not invent facts, gating conditions, action parameters, or assumptions that are not grounded in the provided inputs.
- If a useful field is not grounded, omit it rather than guessing.
- `constraints_mentioned` and `success_criteria` should both be treated as candidate gating conditions.
- Only include a candidate gating condition when it reads like an explicit go/no-go requirement or threshold.
- Do not include aspirational outcome language as a gating condition unless the proposal makes it a gate.
- `what_we_know` should drive normalized facts.
- `what_still_matters` should drive explicit unknowns or unavoidable assumptions.
- Suggest a typed action only when it is well grounded. Otherwise leave `type` null or use a generic type label.
- Use `semi_formal` only when the statement safely maps to one of these supported verifier families:
  - `cash_balance(t) >= N`
  - `runway_months(t) = cash_balance(t)/net_burn(t) >= N`
  - `initiative_budget <= N`
  - `ltv_cac(channel) >= N`
  - `cumulative_units_built(by month M) >= N`
  - `new_sku_contribution_margin >= N`
  - `total_marketing_spend <= N * monthly_revenue`
- If a gating condition does not safely fit one of those families, leave `semi_formal` null.
- Use `action_field_hint` only when a gating threshold obviously corresponds to one action parameter.
- Ground every emitted proof-bearing field in one of:
  - workspace
  - proposal
  - answer
  - stage1_summary
- Include grounding entries for the emitted normalized fields.
- Keep notes concise and non-blocking.
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
    expected_company_id = canonicalize_company_id(workspace_company.name)
    payload = {
        "proposal_id": proposal_id,
        "proposal_text": proposal_text,
        "workspace_company": {
            "id": expected_company_id,
            "name": workspace_company.name,
            "sector": workspace_company.sector,
        },
        "decision_kernel": _build_decision_kernel(ready_result),
        "answers": [
            {"question_id": question_id, "answer": answer}
            for question_id, answer in sorted(answers.items())
        ],
        "normalization_policy": {
            "proof_target": "feasibility_first",
            "action_rule": (
                "Find the concrete proposed action. Use a typed action only when grounded; "
                "otherwise return a generic action shape."
            ),
            "gating_rule": (
                "Treat constraints_mentioned and success_criteria as candidate gating conditions, "
                "but only keep explicit go/no-go requirements."
            ),
            "fact_rule": "Extract measurable known facts from what_we_know without invention.",
            "unknown_rule": (
                "Carry unresolved proof-critical items into unknowns or unavoidable assumptions."
            ),
        },
    }

    log_event(
        settings=settings,
        event="formalization.start",
        payload={
            "proposal_id": proposal_id,
            "expected_company_id": expected_company_id,
        },
        console_message=f"formalization.start proposal_id={proposal_id}",
    )
    output = _call_formalizer_model(client=resolved_client, payload=payload)
    normalized_bundle, battery_document, assembly_notes, grounding_entries = _compile_bundle(
        output.normalized_bundle,
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        ready_result=ready_result,
    )
    grounding_report = GroundingReport(
        entries=_merge_grounding_entries(output.grounding_report.entries, grounding_entries)
    )
    _validate_output_shape(
        battery_document=battery_document,
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        expected_company_id=expected_company_id,
    )
    notes = _merge_notes(
        output.normalized_bundle.notes,
        output.notes,
        assembly_notes,
        _build_grounding_audit_notes(grounding_report, battery_document),
    )
    result = Stage2FormalizationSuccess(
        status="formalized",
        normalized_bundle=normalized_bundle,
        battery_document=battery_document,
        primary_decision_id=proposal_id,
        grounding_report=grounding_report,
        notes=notes,
    )
    log_event(
        settings=settings,
        event="formalization.result",
        payload={
            "proposal_id": proposal_id,
            "status": result.status,
            "grounding_entries": len(result.grounding_report.entries),
            "normalized_bundle": result.normalized_bundle.model_dump(mode="json"),
        },
        console_message=f"formalization.result proposal_id={proposal_id} status={result.status}",
    )
    return result


def _build_decision_kernel(ready_result: Stage1ReadyOutcome) -> dict[str, Any]:
    context = ready_result.working_context
    return {
        "decision": context.decision,
        "objective": context.objective,
        "what_we_know": context.what_we_know,
        "constraints_mentioned": context.constraints_mentioned,
        "success_criteria": context.success_criteria,
        "what_still_matters": context.what_still_matters,
    }


def _resolve_client(
    *,
    settings: OpenRouterSettings | None,
    client: Any | None,
) -> tuple[OpenRouterSettings, Any]:
    if client is not None:
        resolved_settings = settings or get_openrouter_settings(require_api_key=False)
        return resolved_settings, client

    resolved_settings = settings or get_openrouter_settings(require_api_key=False)
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
) -> FormalizationModelOutput:
    try:
        completion = client.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
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
        return FormalizationModelOutput.model_validate_json(completion.raw_model_response)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid JSON"
        raise WorkspaceFormalizationExecutionError(
            f"OpenRouter returned invalid Stage 2 formalization JSON: {error_message}."
        ) from exc


def _build_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "decision_prover_stage2_formalization",
            "strict": True,
            "schema": FormalizationModelOutput.model_json_schema(),
        },
    }


def _validate_output_shape(
    *,
    battery_document: DecisionBattery,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
    expected_company_id: str,
) -> None:
    serialized = battery_document.model_dump(mode="json", by_alias=True)
    canonical_metadata = canonical_battery_metadata()

    for key, expected_value in canonical_metadata.items():
        if serialized.get(key) != expected_value:
            raise WorkspaceFormalizationExecutionError(
                f"Stage 2 formalization must copy canonical battery metadata exactly for '{key}'."
            )

    if len(battery_document.companies) != 1:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization must emit exactly one company."
        )
    if len(battery_document.decisions) != 1:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization must emit exactly one decision."
        )

    company = battery_document.companies[0]
    decision = battery_document.decisions[0]
    if company.id != expected_company_id:
        raise WorkspaceFormalizationExecutionError(
            f"Stage 2 formalization company id must be '{expected_company_id}'."
        )
    if company.name != workspace_company.name:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization company name must match the active workspace name."
        )
    if company.sector != workspace_company.sector:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization company sector must match the active workspace sector."
        )
    if decision.id != proposal_id:
        raise WorkspaceFormalizationExecutionError(
            f"Stage 2 formalization decision id must be '{proposal_id}'."
        )
    if decision.company != expected_company_id:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization decision company must match the emitted company id."
        )
    if decision.proposal != proposal_text:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization decision proposal must match the original proposal text."
        )


def _compile_bundle(
    bundle: NormalizedFeasibilityBundle,
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
    ready_result: Stage1ReadyOutcome,
) -> tuple[NormalizedFeasibilityBundle, DecisionBattery, list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    expected_company_id = canonicalize_company_id(workspace_company.name)

    compiled_facts, fact_notes, fact_grounding = _compile_facts(bundle.facts, ready_result)
    notes.extend(fact_notes)
    grounding_entries.extend(fact_grounding)

    compiled_action, action_notes, action_grounding = _compile_action(
        bundle.action,
        bundle.gating_conditions,
        ready_result,
    )
    notes.extend(action_notes)
    grounding_entries.extend(action_grounding)

    compiled_constraints, kept_gating_conditions, gating_notes, gating_grounding = _compile_gating_conditions(
        bundle.gating_conditions,
        ready_result,
    )
    notes.extend(gating_notes)
    grounding_entries.extend(gating_grounding)

    compiled_assumptions, assumption_notes, assumption_grounding = _compile_assumptions(
        bundle.assumptions,
        bundle.unknowns,
        ready_result,
    )
    notes.extend(assumption_notes)
    grounding_entries.extend(assumption_grounding)

    kept_unknowns = _compile_unknowns(bundle.unknowns, ready_result)
    normalized_bundle = NormalizedFeasibilityBundle(
        action=NormalizedAction(
            statement=compiled_action["statement"],
            type=compiled_action["type"],
            parameters=compiled_action["parameters"],
        ),
        facts=compiled_facts["normalized"],
        gating_conditions=kept_gating_conditions,
        assumptions=compiled_assumptions["normalized"],
        unknowns=kept_unknowns,
        notes=_merge_notes(bundle.notes),
    )

    payload = canonical_battery_metadata()
    payload["companies"] = [
        {
            "id": expected_company_id,
            "name": workspace_company.name,
            "sector": workspace_company.sector,
            "facts": compiled_facts["battery"],
            "constraints": compiled_constraints,
        }
    ]
    payload["decisions"] = [
        {
            "id": proposal_id,
            "company": expected_company_id,
            "proposal": proposal_text,
            "action": compiled_action["battery"],
            "objective": ready_result.working_context.objective,
            "stated_assumptions": compiled_assumptions["battery"],
        }
    ]
    try:
        battery_document = DecisionBattery.model_validate(payload)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid formalization payload"
        raise WorkspaceFormalizationExecutionError(
            f"OpenRouter returned invalid Stage 2 formalization payload: {error_message}."
        ) from exc

    return normalized_bundle, battery_document, notes, grounding_entries


def _compile_facts(
    facts: list[NormalizedFact],
    ready_result: Stage1ReadyOutcome,
) -> tuple[dict[str, Any], list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    normalized_items: list[NormalizedFact] = []
    battery_facts: dict[str, CompanyFact] = {}
    conflicts: set[str] = set()

    for fact in facts:
        key = fact.key.strip()
        if not key or key in conflicts:
            continue

        normalized_fact = NormalizedFact(
            key=key,
            value=fact.value,
            unit=fact.unit.strip(),
            statement=fact.statement.strip(),
        )
        existing = battery_facts.get(key)
        if existing is None:
            battery_facts[key] = CompanyFact(value=normalized_fact.value, unit=normalized_fact.unit)
            normalized_items.append(normalized_fact)
            grounding_entries.append(
                _grounded_entry(
                    field=f"companies[0].facts.{key}",
                    statement=normalized_fact.statement,
                    ready_result=ready_result,
                )
            )
            continue

        if existing.value == normalized_fact.value and existing.unit == normalized_fact.unit:
            continue

        conflicts.add(key)
        battery_facts.pop(key, None)
        normalized_items = [item for item in normalized_items if item.key != key]
        notes.append(
            f"Formalization note: conflicting normalized fact values for '{key}' were omitted from the final battery."
        )

    return {"normalized": normalized_items, "battery": battery_facts}, notes, grounding_entries


def _compile_action(
    action: NormalizedAction,
    gating_conditions: list[NormalizedGatingCondition],
    ready_result: Stage1ReadyOutcome,
) -> tuple[dict[str, Any], list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    statement = action.statement.strip() or ready_result.working_context.decision.strip()
    if not statement:
        raise WorkspaceFormalizationExecutionError(
            "Stage 2 formalization could not identify a concrete action statement."
        )

    raw_type = action.type.strip() if action.type else None
    raw_parameters = {
        key: value
        for key, value in action.parameters.items()
        if key.strip() and _is_json_compatible(value)
    }
    dropped_parameter_keys = sorted(set(action.parameters) - set(raw_parameters))
    for key in dropped_parameter_keys:
        notes.append(
            f"Formalization note: action parameter '{key}' was dropped because it was not JSON-compatible."
        )

    enriched_parameters = dict(raw_parameters)
    if raw_type and raw_type in ACTION_REGISTRY:
        for condition in gating_conditions:
            field = (condition.action_field_hint or "").strip()
            if not field or field in enriched_parameters or condition.value is None:
                continue
            candidate = {"type": raw_type, **enriched_parameters, field: condition.value}
            try:
                validate_action_payload(candidate)
            except (TypeError, ValueError, ValidationError):
                continue
            enriched_parameters[field] = condition.value
            notes.append(
                f"Formalization note: gating condition '{condition.statement}' enriched action field '{field}'."
            )
            grounding_entries.append(
                _grounded_entry(
                    field=f"decisions[0].action.{field}",
                    statement=condition.statement,
                    ready_result=ready_result,
                )
            )

    if raw_type:
        typed_payload, typed_parameters, typed_notes, typed_grounding = _build_action_payload(
            action_type=raw_type,
            parameters=enriched_parameters,
            statement=statement,
            ready_result=ready_result,
        )
        notes.extend(typed_notes)
        grounding_entries.extend(typed_grounding)
        if typed_payload is not None:
            return {
                "statement": statement,
                "type": typed_payload["type"],
                "parameters": typed_parameters,
                "battery": typed_payload,
            }, notes, grounding_entries

    notes.append(
        "Formalization note: a generic fallback action was used because no valid typed action payload was available."
    )
    grounding_entries.append(
        _grounded_entry(
            field="decisions[0].action.summary",
            statement=statement,
            ready_result=ready_result,
        )
    )
    generic_parameters = dict(enriched_parameters)
    generic_payload = {
        "type": "generic_decision",
        "summary": statement,
        **generic_parameters,
    }
    validate_action_payload(generic_payload)
    return {
        "statement": statement,
        "type": "generic_decision",
        "parameters": generic_parameters,
        "battery": generic_payload,
    }, notes, grounding_entries


def _build_action_payload(
    *,
    action_type: str,
    parameters: dict[str, JsonValue],
    statement: str,
    ready_result: Stage1ReadyOutcome,
) -> tuple[dict[str, Any] | None, dict[str, JsonValue], list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    if action_type not in ACTION_REGISTRY:
        return None, {}, notes, grounding_entries

    kept_parameters: dict[str, JsonValue] = {}
    for key, value in parameters.items():
        candidate = {"type": action_type, **kept_parameters, key: value}
        try:
            validate_action_payload(candidate)
        except (TypeError, ValueError, ValidationError):
            notes.append(
                f"Formalization note: action parameter '{key}' was dropped because it did not validate for action type '{action_type}'."
            )
            continue
        kept_parameters[key] = value
        grounding_entries.append(
            _grounded_entry(
                field=f"decisions[0].action.{key}",
                statement=statement,
                ready_result=ready_result,
            )
        )

    payload = {"type": action_type, **kept_parameters}
    try:
        validate_action_payload(payload)
    except (TypeError, ValueError, ValidationError):
        return None, {}, notes, grounding_entries
    return payload, kept_parameters, notes, grounding_entries


def _compile_gating_conditions(
    gating_conditions: list[NormalizedGatingCondition],
    ready_result: Stage1ReadyOutcome,
) -> tuple[list[Constraint], list[NormalizedGatingCondition], list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    compiled_constraints: list[Constraint] = []
    kept_conditions: list[NormalizedGatingCondition] = []
    seen: set[tuple[str, str, str | None]] = set()

    for condition in gating_conditions:
        statement = condition.statement.strip()
        if not statement:
            continue
        normalized_condition = NormalizedGatingCondition(
            statement=statement,
            kind=condition.kind,
            semi_formal=_normalize_optional_text(condition.semi_formal),
            metric_key=_normalize_optional_text(condition.metric_key),
            operator=_normalize_optional_text(condition.operator),
            value=condition.value,
            unit=_normalize_optional_text(condition.unit),
            action_field_hint=_normalize_optional_text(condition.action_field_hint),
        )
        dedupe_key = (
            normalized_condition.statement,
            normalized_condition.kind,
            normalized_condition.semi_formal,
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        kept_conditions.append(normalized_condition)

        if not normalized_condition.semi_formal:
            notes.append(
                f"Formalization note: gating condition '{statement}' stayed visible in the normalized bundle but was not compiled because no supported semi-formal expression was available."
            )
            continue
        if not _is_supported_constraint_expression(normalized_condition.semi_formal):
            notes.append(
                f"Formalization note: gating condition '{statement}' stayed visible in the normalized bundle but was not compiled because its semi-formal expression is outside current verifier coverage."
            )
            continue

        constraint_id = f"H-C{len(compiled_constraints) + 1}"
        compiled_constraints.append(
            Constraint(
                id=constraint_id,
                kind="hard",
                statement=normalized_condition.statement,
                semi_formal=normalized_condition.semi_formal,
            )
        )
        grounding_entries.append(
            _grounded_entry(
                field=f"companies[0].constraints[{len(compiled_constraints) - 1}]",
                statement=normalized_condition.statement,
                ready_result=ready_result,
            )
        )

    return compiled_constraints, kept_conditions, notes, grounding_entries


def _compile_assumptions(
    assumptions: list[NormalizedAssumption],
    unknowns: list[str],
    ready_result: Stage1ReadyOutcome,
) -> tuple[dict[str, Any], list[str], list[GroundingEntry]]:
    notes: list[str] = []
    grounding_entries: list[GroundingEntry] = []
    normalized_items: list[NormalizedAssumption] = []
    battery_assumptions: list[StatedAssumption] = []
    seen: set[tuple[str, str]] = set()

    for assumption in assumptions:
        statement = assumption.statement.strip()
        if not statement:
            continue
        normalized_assumption = NormalizedAssumption(statement=statement, status=assumption.status)
        dedupe_key = (normalized_assumption.statement, normalized_assumption.status)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_items.append(normalized_assumption)
        battery_assumptions.append(
            StatedAssumption(
                id=f"A{len(battery_assumptions) + 1}",
                statement=normalized_assumption.statement,
                status=normalized_assumption.status,
            )
        )
        grounding_entries.append(
            _grounded_entry(
                field=f"decisions[0].stated_assumptions[{len(battery_assumptions) - 1}]",
                statement=normalized_assumption.statement,
                ready_result=ready_result,
            )
        )

    if not normalized_items and unknowns:
        notes.append(
            "Formalization note: unresolved proof-critical items remained as unknowns and were not promoted into stated assumptions."
        )

    return {"normalized": normalized_items, "battery": battery_assumptions}, notes, grounding_entries


def _compile_unknowns(unknowns: list[str], ready_result: Stage1ReadyOutcome) -> list[str]:
    if unknowns:
        return _dedupe_strings(unknowns)
    return _dedupe_strings(ready_result.working_context.what_still_matters)


def _grounded_entry(
    *,
    field: str,
    statement: str,
    ready_result: Stage1ReadyOutcome,
) -> GroundingEntry:
    locator, quote = _find_kernel_source(statement, ready_result)
    source_type = "proposal" if locator == "proposal_text" else "stage1_summary"
    return GroundingEntry(
        field=field,
        source_type=source_type,
        source_quote=quote,
        source_locator=locator,
    )


def _find_kernel_source(statement: str, ready_result: Stage1ReadyOutcome) -> tuple[str, str]:
    target = _normalize_match_text(statement)
    if not target:
        return "working_context", statement

    context = ready_result.working_context
    candidates = [
        ("proposal_text", ready_result.proposal),
        ("working_context.decision", context.decision),
        ("working_context.objective", context.objective),
    ]
    candidates.extend(
        (f"working_context.what_we_know[{index}]", value)
        for index, value in enumerate(context.what_we_know)
    )
    candidates.extend(
        (f"working_context.constraints_mentioned[{index}]", value)
        for index, value in enumerate(context.constraints_mentioned)
    )
    candidates.extend(
        (f"working_context.success_criteria[{index}]", value)
        for index, value in enumerate(context.success_criteria)
    )
    candidates.extend(
        (f"working_context.what_still_matters[{index}]", value)
        for index, value in enumerate(context.what_still_matters)
    )
    candidates.extend(
        (f"unresolved_notes[{index}]", value)
        for index, value in enumerate(ready_result.unresolved_notes)
    )

    for locator, candidate in candidates:
        normalized = _normalize_match_text(candidate)
        if not normalized:
            continue
        if normalized == target or normalized in target or target in normalized:
            return locator, candidate
    return "working_context", statement


def _merge_grounding_entries(
    base_entries: list[GroundingEntry],
    extra_entries: list[GroundingEntry],
) -> list[GroundingEntry]:
    merged: list[GroundingEntry] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry in [*base_entries, *extra_entries]:
        key = (
            entry.field,
            entry.source_type,
            entry.source_quote,
            entry.source_locator,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    return merged


def _build_grounding_audit_notes(
    grounding_report: GroundingReport,
    battery_document: DecisionBattery,
) -> list[str]:
    company = battery_document.companies[0]
    decision = battery_document.decisions[0]
    grounded_fields = {entry.field for entry in grounding_report.entries}
    missing_by_category: dict[str, list[str]] = defaultdict(list)

    for fact_key in sorted(company.facts):
        field = f"companies[0].facts.{fact_key}"
        if _has_grounding(field, grounded_fields, allow_descendants=True):
            continue
        missing_by_category["facts"].append(field)

    for index, _constraint in enumerate(company.constraints):
        field = f"companies[0].constraints[{index}]"
        if _has_grounding(field, grounded_fields, allow_descendants=True):
            continue
        missing_by_category["constraints"].append(field)

    action_payload = decision.action.model_dump(mode="json", exclude_none=True)
    for key in sorted(action_payload):
        if key == "type":
            continue
        field = f"decisions[0].action.{key}"
        if _has_grounding(field, grounded_fields):
            continue
        missing_by_category["action parameters"].append(field)

    for index, _assumption in enumerate(decision.stated_assumptions):
        field = f"decisions[0].stated_assumptions[{index}]"
        if _has_grounding(field, grounded_fields, allow_descendants=True):
            continue
        missing_by_category["assumptions"].append(field)

    notes: list[str] = []
    for category in ("facts", "constraints", "action parameters", "assumptions"):
        fields = missing_by_category.get(category)
        if not fields:
            continue
        notes.append(
            "Grounding audit warning: missing grounding entries for "
            f"{category}: {', '.join(fields)}."
        )
    return notes


def _has_grounding(
    field: str,
    grounded_fields: set[str],
    *,
    allow_descendants: bool = False,
) -> bool:
    if field in grounded_fields:
        return True
    if not allow_descendants:
        return False
    prefix = f"{field}."
    return any(candidate.startswith(prefix) for candidate in grounded_fields)


def _is_supported_constraint_expression(expression: str) -> bool:
    normalized = " ".join(expression.split())
    return normalized.startswith(
        (
            "cash_balance(t) >=",
            "runway_months(t) = cash_balance(t)/net_burn(t) >=",
            "initiative_budget <=",
            "ltv_cac(channel) >=",
            "cumulative_units_built(",
            "new_sku_contribution_margin >=",
            "total_marketing_spend <=",
        )
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_match_text(value: str) -> str:
    return " ".join(value.lower().split())


def _dedupe_strings(values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_compatible(item) for key, item in value.items())
    return False


def _merge_notes(*note_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for note_group in note_groups:
        for note in note_group:
            normalized = note.strip()
            if not normalized or normalized in merged:
                continue
            merged.append(normalized)
    return merged
