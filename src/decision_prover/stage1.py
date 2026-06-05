from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .constants import DEFAULT_BATTERY_PATH
from .contracts.actions import validate_action_payload
from .contracts.battery import Company, CompanyFact, Constraint, Decision, DecisionBattery, StatedAssumption
from .contracts.output import (
    ClarificationNeededOutcome,
    FormalizedOutcome,
    GroundingReport,
    GroundingReportEntry,
    OperationStatus,
    Stage1Gap,
    Stage1Question,
    Stage1RunRequest,
    Stage1RunResponse,
    Stage1TranscriptTurn,
)
from .fixtures import load_battery_fixture
from .proposals import ProposalFixture, ProposalPrompt
from .settings import ConfigurationError, OpenRouterSettings, get_openrouter_settings

SUPPORTED_ACTIONS: dict[str, dict[str, Any]] = {
    "hire": {
        "description": "Hiring additional people.",
        "required_action_fields": ["count", "role", "fully_loaded_cost_per_year"],
        "required_fact_keys": ["headcount"],
        "required_constraint_families": [],
    },
    "channel_test": {
        "description": "Testing or scaling an acquisition or marketing channel.",
        "required_action_fields": ["projected_cac", "projected_arpu_monthly"],
        "required_fact_keys": ["gross_margin", "monthly_churn_rate"],
        "required_constraint_families": ["ltv_cac_minimum"],
    },
    "acquisition": {
        "description": "Acquiring another company or business line.",
        "required_action_fields": ["cash_cost", "added_mrr"],
        "required_fact_keys": [],
        "required_constraint_families": [],
    },
    "one_time_spend": {
        "description": "A one-time spend such as a campaign or initiative.",
        "required_action_fields": ["cash_cost", "label"],
        "required_fact_keys": [],
        "required_constraint_families": [],
    },
    "price_change": {
        "description": "Changing price for a product, plan, or customer segment.",
        "required_action_fields": [],
        "required_fact_keys": [],
        "required_constraint_families": [],
    },
    "accept_order": {
        "description": "Accepting an order with a delivery deadline.",
        "required_action_fields": ["units", "due_months", "unit_price"],
        "required_fact_keys": ["production_capacity", "backlog_units"],
        "required_constraint_families": ["capacity_backlog"],
    },
    "capex_expansion": {
        "description": "A capital expansion that changes production capacity.",
        "required_action_fields": ["cost", "capacity_from", "capacity_to", "ramp_months"],
        "required_fact_keys": [],
        "required_constraint_families": ["capacity_backlog"],
    },
    "launch_sku": {
        "description": "Launching a new SKU or line extension.",
        "required_action_fields": ["launch_cost", "projected_monthly_revenue", "contribution_margin"],
        "required_fact_keys": [],
        "required_constraint_families": ["new_sku_margin"],
    },
    "marketing_increase": {
        "description": "Increasing ongoing marketing spend.",
        "required_action_fields": ["added_monthly_spend", "target"],
        "required_fact_keys": ["current_marketing_spend", "monthly_revenue"],
        "required_constraint_families": ["marketing_spend_cap"],
    },
    "discontinue_line": {
        "description": "Discontinuing one product line and reallocating resources.",
        "required_action_fields": ["line", "reallocate_to"],
        "required_fact_keys": ["line_B_revenue", "line_B_contribution_margin"],
        "required_constraint_families": [],
    },
    "retention_program": {
        "description": "Investing in a program to reduce churn or improve retention.",
        "required_action_fields": ["cost", "churn_from", "churn_to"],
        "required_fact_keys": ["gross_margin", "arpu_monthly"],
        "required_constraint_families": [],
    },
    "supplier_renegotiation": {
        "description": "Renegotiating supplier terms to improve margin.",
        "required_action_fields": ["cost", "line_A_cogs_reduction_pts"],
        "required_fact_keys": ["line_A_contribution_margin"],
        "required_constraint_families": [],
    },
}

QUESTION_PRIORITY = {
    "scope": 0,
    "company.name": 1,
    "company.sector": 2,
    "objective": 3,
}


class Stage1InputError(ValueError):
    """Raised when Stage 1 request inputs are invalid."""


class Stage1ExecutionError(RuntimeError):
    """Raised when the Stage 1 AI planner cannot produce a usable result."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannerEvidence(StrictModel):
    field: str = Field(min_length=1)
    source_type: Literal["proposal", "answer"]
    source_quote: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)


class PlannerCompany(StrictModel):
    id: str | None = None
    name: str | None = None
    sector: str | None = None
    facts: dict[str, CompanyFact] = Field(default_factory=dict)
    constraints: list[Constraint] = Field(default_factory=list)


class PlannerDecision(StrictModel):
    id: str | None = None
    company: str | None = None
    proposal: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    objective: str | None = None
    stated_assumptions: list[StatedAssumption] = Field(default_factory=list)


class PlannerGap(StrictModel):
    category: Literal[
        "action_details",
        "company_fact",
        "company_metadata",
        "hard_constraint",
        "objective",
        "scope",
    ]
    field: str = Field(min_length=1)
    verification_check: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PlannerQuestion(StrictModel):
    field: str = Field(min_length=1)
    verification_check: str = Field(min_length=1)
    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class Stage1PlannerOutput(StrictModel):
    scope_status: Literal["supported_family", "unsupported_family", "ambiguous_family"]
    action_family: str | None = None
    ignored_details: list[str] = Field(default_factory=list)
    companies: list[PlannerCompany] = Field(default_factory=list)
    decisions: list[PlannerDecision] = Field(default_factory=list)
    gaps: list[PlannerGap] = Field(default_factory=list)
    questions: list[PlannerQuestion] = Field(default_factory=list)
    evidence: list[PlannerEvidence] = Field(default_factory=list)


@dataclass(slots=True)
class _PreparedAnswer:
    question_id: str
    field: str
    question: str
    answer: str


def run_stage1(
    proposal_fixture: ProposalFixture,
    request: Stage1RunRequest | None = None,
    *,
    settings: OpenRouterSettings | None = None,
    client: Any | None = None,
) -> Stage1RunResponse:
    request = request or Stage1RunRequest()
    proposal_lookup = {proposal.id: proposal for proposal in proposal_fixture.proposals}
    selected_ids = request.proposal_ids or [proposal.id for proposal in proposal_fixture.proposals]

    for proposal_id in selected_ids:
        if proposal_id not in proposal_lookup:
            raise Stage1InputError(f"Unknown proposal id '{proposal_id}'.")
    for proposal_id in request.answers:
        if proposal_id not in proposal_lookup:
            raise Stage1InputError(f"Answers were provided for unknown proposal id '{proposal_id}'.")
        if proposal_id not in selected_ids:
            raise Stage1InputError(
                f"Answers were provided for proposal '{proposal_id}' but it was not selected."
            )

    settings, resolved_client = _resolve_client(settings=settings, client=client)
    results = [
        _run_single_proposal(
            proposal_lookup[proposal_id],
            request.answers.get(proposal_id, {}),
            settings=settings,
            client=resolved_client,
        )
        for proposal_id in selected_ids
    ]
    return Stage1RunResponse(
        status=OperationStatus(
            state="stage1_complete",
            message="Stage 1 AI planning complete.",
        ),
        title=proposal_fixture.title,
        results=results,
    )


def _resolve_client(
    *,
    settings: OpenRouterSettings | None,
    client: Any | None,
) -> tuple[OpenRouterSettings | None, Any]:
    if client is not None:
        return settings, client

    settings = settings or get_openrouter_settings(require_api_key=True)
    try:
        from .ai.client import OpenRouterClient
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without dependencies
        raise ConfigurationError(
            "Stage 1 AI requires project dependencies to be installed before OpenRouter can be used."
        ) from exc
    return settings, OpenRouterClient(settings)


def _run_single_proposal(
    proposal: ProposalPrompt,
    answers: dict[str, str],
    *,
    settings: OpenRouterSettings | None,
    client: Any,
) -> ClarificationNeededOutcome | FormalizedOutcome:
    transcript = [
        Stage1TranscriptTurn(
            speaker="user",
            kind="proposal",
            text=proposal.text,
        )
    ]

    prepared_answers: list[_PreparedAnswer] = []
    if answers:
        initial_plan = _plan_proposal(
            proposal=proposal,
            prepared_answers=[],
            settings=settings,
            client=client,
        )
        initial_questions = _questions_by_id(
            proposal_id=proposal.id,
            gaps=initial_plan.gaps,
            questions=initial_plan.questions,
        )
        unknown_answers = sorted(set(answers) - set(initial_questions))
        if unknown_answers:
            raise Stage1InputError(
                f"{proposal.id}: unexpected answer keys {', '.join(unknown_answers)}."
            )
        for question_id, question in initial_questions.items():
            answer_text = answers.get(question_id)
            if answer_text is None:
                continue
            cleaned = answer_text.strip()
            if not cleaned:
                continue
            prepared_answers.append(
                _PreparedAnswer(
                    question_id=question_id,
                    field=question.field,
                    question=question.question,
                    answer=cleaned,
                )
            )
            transcript.append(
                Stage1TranscriptTurn(
                    speaker="assistant",
                    kind="question",
                    text=question.question,
                    question_id=question_id,
                )
            )
            transcript.append(
                Stage1TranscriptTurn(
                    speaker="user",
                    kind="answer",
                    text=cleaned,
                    question_id=question_id,
                )
            )

    plan = _plan_proposal(
        proposal=proposal,
        prepared_answers=prepared_answers,
        settings=settings,
        client=client,
    )
    return _materialize_outcome(
        proposal=proposal,
        plan=plan,
        prepared_answers=prepared_answers,
        transcript=transcript,
    )


def _plan_proposal(
    *,
    proposal: ProposalPrompt,
    prepared_answers: list[_PreparedAnswer],
    settings: OpenRouterSettings | None,
    client: Any,
) -> Stage1PlannerOutput:
    try:
        completion = client.create_chat_completion(
            messages=_build_messages(proposal=proposal, prepared_answers=prepared_answers),
            response_format=_build_response_format(),
        )
    except Exception as exc:  # pragma: no cover - provider path covered by tests through fake clients
        if exc.__class__.__name__ == "OpenRouterError":
            raise Stage1ExecutionError(str(exc)) from exc
        raise

    try:
        return Stage1PlannerOutput.model_validate_json(completion.raw_model_response)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid planner JSON"
        raise Stage1ExecutionError(
            f"OpenRouter returned invalid Stage 1 planner JSON: {error_message}."
        ) from exc


def _build_messages(
    *,
    proposal: ProposalPrompt,
    prepared_answers: list[_PreparedAnswer],
) -> list[dict[str, str]]:
    payload = {
        "proposal_id": proposal.id,
        "proposal_text": proposal.text,
        "supported_action_families": [
            {
                "action_family": action_family,
                "description": spec["description"],
                "required_action_fields": spec["required_action_fields"],
            }
            for action_family, spec in SUPPORTED_ACTIONS.items()
        ],
        "prior_answers": [
            {
                "question_id": answer.question_id,
                "field": answer.field,
                "question": answer.question,
                "answer": answer.answer,
            }
            for answer in prepared_answers
        ],
    }
    return [
        {"role": "system", "content": _stage1_system_prompt()},
        {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
    ]


def _stage1_system_prompt() -> str:
    return """You are the Stage 1 planner for a business Decision Prover.
Return JSON only. Do not wrap it in markdown.

Your job is to extract a proposal into a verifier-scoped structured draft without inventing any fact.

Hard rules:
- Never invent or infer a missing company name, sector, fact, constraint, number, action parameter, or assumption.
- You may normalize explicit values, for example "$2M" -> 2000000 and "six months" -> 6.
- If a value is not explicitly stated in the proposal or prior answers, leave it out and add a blocking gap plus a clarification question.
- Do not create likely constraints from generic business practice.
- Stay inside the supported action families supplied by the user payload. If the proposal does not clearly fit one, return scope_status as unsupported_family or ambiguous_family.
- Every extracted semantic field must have one evidence record with an exact source quote from either the proposal text or an answer text.
- Use source_locator "proposal" for proposal quotes, or the provided question_id for answer quotes.

Required output shape:
- scope_status
- action_family
- ignored_details
- companies[]
- decisions[]
- gaps[]
- questions[]
- evidence[]

Evidence field path conventions:
- companies[0].name
- companies[0].sector
- companies[0].facts.<fact_key>
- companies[0].constraints[<index>]
- decisions[0].action.type
- decisions[0].action.<field_name>
- decisions[0].objective
- decisions[0].stated_assumptions[<index>]

Questioning policy:
- Ask only clarification questions that unlock a concrete verifier need.
- Ask for company name and sector if they are missing.
- Ask in batches: include all currently blocking questions in the same response.
"""


def _build_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "decision_prover_stage1_plan",
            "strict": True,
            "schema": Stage1PlannerOutput.model_json_schema(),
        },
    }


def _materialize_outcome(
    *,
    proposal: ProposalPrompt,
    plan: Stage1PlannerOutput,
    prepared_answers: list[_PreparedAnswer],
    transcript: list[Stage1TranscriptTurn],
) -> ClarificationNeededOutcome | FormalizedOutcome:
    grounding_lookup = _validated_grounding_lookup(
        proposal_text=proposal.text,
        prepared_answers=prepared_answers,
        evidence=plan.evidence,
    )
    scope_status = _normalized_scope_status(plan)
    action_type = plan.action_family if plan.action_family in SUPPORTED_ACTIONS else None

    ai_gaps = _normalize_planner_gaps(
        proposal_id=proposal.id,
        gaps=plan.gaps,
    )
    ai_questions = _questions_by_field(
        proposal_id=proposal.id,
        gaps=plan.gaps,
        questions=plan.questions,
    )

    company_data, company_grounding = _prepare_company(plan=plan, grounding_lookup=grounding_lookup)
    decision_data, decision_grounding = _prepare_decision(
        proposal=proposal,
        plan=plan,
        grounding_lookup=grounding_lookup,
    )
    blocking_gaps = _compute_blocking_gaps(
        proposal_id=proposal.id,
        scope_status=scope_status,
        action_type=action_type,
        company_data=company_data,
        decision_data=decision_data,
        ai_gaps=ai_gaps,
    )
    question_map = _build_question_map(
        proposal_id=proposal.id,
        gaps=blocking_gaps,
        ai_questions=ai_questions,
    )

    for question in question_map.values():
        if question.id in {answer.question_id for answer in prepared_answers}:
            continue
        transcript.append(
            Stage1TranscriptTurn(
                speaker="assistant",
                kind="question",
                text=question.question,
                question_id=question.id,
            )
        )

    if blocking_gaps:
        return ClarificationNeededOutcome(
            outcome="clarification_needed",
            proposal_id=proposal.id,
            proposal=proposal.text,
            scope_status=scope_status,
            action_type=action_type,
            objective=decision_data.get("objective"),
            blocking_fields=[gap.field for gap in blocking_gaps],
            gaps=blocking_gaps,
            questions=list(question_map.values()),
            ignored_details=plan.ignored_details,
            transcript=transcript,
        )

    battery_document, primary_decision_id = _build_battery_document(
        proposal_id=proposal.id,
        proposal_text=proposal.text,
        company_data=company_data,
        decision_data=decision_data,
    )
    grounding_report = GroundingReport(entries=company_grounding + decision_grounding)
    transcript.append(
        Stage1TranscriptTurn(
            speaker="assistant",
            kind="formalization",
            text=(
                f"Formalized {proposal.id} into a battery-shaped document with primary decision"
                f" '{primary_decision_id}'."
            ),
        )
    )
    return FormalizedOutcome(
        outcome="formalized",
        proposal_id=proposal.id,
        proposal=proposal.text,
        battery_document=battery_document,
        primary_decision_id=primary_decision_id,
        grounding_report=grounding_report,
        ignored_details=plan.ignored_details,
        transcript=transcript,
    )


def _validated_grounding_lookup(
    *,
    proposal_text: str,
    prepared_answers: list[_PreparedAnswer],
    evidence: list[PlannerEvidence],
) -> dict[str, GroundingReportEntry]:
    answer_lookup = {answer.question_id: answer.answer for answer in prepared_answers}
    grounding_lookup: dict[str, GroundingReportEntry] = {}
    for item in evidence:
        source_text: str | None = None
        if item.source_type == "proposal":
            if item.source_locator != "proposal":
                continue
            source_text = proposal_text
        elif item.source_type == "answer":
            source_text = answer_lookup.get(item.source_locator)
        if source_text is None:
            continue
        if not _quote_matches_source(item.source_quote, source_text):
            continue
        grounding_lookup[item.field] = GroundingReportEntry(
            field=item.field,
            source_type=item.source_type,
            source_quote=item.source_quote,
            source_locator=item.source_locator,
        )
    return grounding_lookup


def _quote_matches_source(source_quote: str, source_text: str) -> bool:
    return _normalize_text(source_quote) in _normalize_text(source_text)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = normalized.replace("“", '"').replace("”", '"').replace("’", "'")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalized_scope_status(plan: Stage1PlannerOutput) -> Literal["supported_family", "unsupported_family", "ambiguous_family"]:
    if plan.scope_status != "supported_family":
        return plan.scope_status
    if plan.action_family not in SUPPORTED_ACTIONS:
        return "unsupported_family"
    return "supported_family"


def _prepare_company(
    *,
    plan: Stage1PlannerOutput,
    grounding_lookup: dict[str, GroundingReportEntry],
) -> tuple[dict[str, Any], list[GroundingReportEntry]]:
    if not plan.companies:
        return {"name": None, "sector": None, "facts": {}, "constraints": []}, []
    company = plan.companies[0]
    prepared: dict[str, Any] = {
        "name": company.name if "companies[0].name" in grounding_lookup else None,
        "sector": company.sector if "companies[0].sector" in grounding_lookup else None,
        "facts": {},
        "constraints": [],
    }
    entries: list[GroundingReportEntry] = []
    for field_path in ["companies[0].name", "companies[0].sector"]:
        entry = grounding_lookup.get(field_path)
        if entry is not None:
            entries.append(entry)

    for fact_key, fact in company.facts.items():
        field_path = f"companies[0].facts.{fact_key}"
        entry = grounding_lookup.get(field_path)
        if entry is None:
            continue
        prepared["facts"][fact_key] = fact
        entries.append(entry)

    for index, constraint in enumerate(company.constraints):
        field_path = f"companies[0].constraints[{index}]"
        entry = grounding_lookup.get(field_path)
        if entry is None:
            continue
        prepared["constraints"].append(constraint)
        entries.append(entry)
    return prepared, entries


def _prepare_decision(
    *,
    proposal: ProposalPrompt,
    plan: Stage1PlannerOutput,
    grounding_lookup: dict[str, GroundingReportEntry],
) -> tuple[dict[str, Any], list[GroundingReportEntry]]:
    if not plan.decisions:
        return {"action": {}, "objective": None, "assumptions": []}, []
    decision = plan.decisions[0]
    prepared_action: dict[str, Any] = {}
    entries: list[GroundingReportEntry] = []
    for key, value in decision.action.items():
        field_path = f"decisions[0].action.{key}"
        entry = grounding_lookup.get(field_path)
        if entry is None:
            continue
        prepared_action[key] = value
        entries.append(entry)
    objective = decision.objective if "decisions[0].objective" in grounding_lookup else None
    objective_entry = grounding_lookup.get("decisions[0].objective")
    if objective_entry is not None:
        entries.append(objective_entry)

    prepared_assumptions: list[StatedAssumption] = []
    for index, assumption in enumerate(decision.stated_assumptions):
        field_path = f"decisions[0].stated_assumptions[{index}]"
        entry = grounding_lookup.get(field_path)
        if entry is None:
            continue
        prepared_assumptions.append(assumption)
        entries.append(entry)

    return {
        "proposal": decision.proposal or proposal.text,
        "action": prepared_action,
        "objective": objective,
        "assumptions": prepared_assumptions,
    }, entries


def _compute_blocking_gaps(
    *,
    proposal_id: str,
    scope_status: Literal["supported_family", "unsupported_family", "ambiguous_family"],
    action_type: str | None,
    company_data: dict[str, Any],
    decision_data: dict[str, Any],
    ai_gaps: list[Stage1Gap],
) -> list[Stage1Gap]:
    gap_map = {gap.field: gap for gap in ai_gaps}

    def ensure_gap(
        *,
        field: str,
        category: Literal[
            "action_details",
            "company_fact",
            "company_metadata",
            "hard_constraint",
            "objective",
            "scope",
        ],
        verification_check: str,
        reason: str,
    ) -> None:
        if field in gap_map:
            return
        gap_map[field] = Stage1Gap(
            id=_gap_id(proposal_id, field),
            category=category,
            field=field,
            verification_check=verification_check,
            reason=reason,
        )

    if scope_status == "unsupported_family":
        ensure_gap(
            field="scope",
            category="scope",
            verification_check="select_supported_action_family",
            reason="The proposal does not yet map cleanly to a supported verifier action family.",
        )
    elif scope_status == "ambiguous_family":
        ensure_gap(
            field="scope",
            category="scope",
            verification_check="disambiguate_action_family",
            reason="The proposal could map to multiple verifier action families and needs disambiguation.",
        )

    if company_data.get("name") is None:
        ensure_gap(
            field="company.name",
            category="company_metadata",
            verification_check="identify_company",
            reason="The company name is required for a final battery-shaped formalization.",
        )
    if company_data.get("sector") is None:
        ensure_gap(
            field="company.sector",
            category="company_metadata",
            verification_check="identify_sector",
            reason="The company sector is required for a final battery-shaped formalization.",
        )
    if decision_data.get("objective") is None:
        ensure_gap(
            field="objective",
            category="objective",
            verification_check="formalize_objective",
            reason="The business objective is missing or not grounded explicitly enough to formalize.",
        )

    action = decision_data.get("action", {})
    if not action_type:
        ensure_gap(
            field="action.type",
            category="scope",
            verification_check="formalize_action_family",
            reason="The supported action family could not be grounded from the proposal.",
        )
    else:
        if "type" not in action:
            ensure_gap(
                field="action.type",
                category="action_details",
                verification_check="formalize_action_family",
                reason="The action type is missing from the formalized decision payload.",
            )
        for field_name in _required_action_fields(action_type, action):
            if field_name not in action:
                ensure_gap(
                    field=f"action.{field_name}",
                    category="action_details",
                    verification_check="formalize_action_payload",
                    reason=f"The action field '{field_name}' is required for action type '{action_type}'.",
                )

        for fact_key in SUPPORTED_ACTIONS.get(action_type, {}).get("required_fact_keys", []):
            if fact_key not in company_data.get("facts", {}):
                ensure_gap(
                    field=f"company.facts.{fact_key}",
                    category="company_fact",
                    verification_check="ground_required_company_fact",
                    reason=f"The fact '{fact_key}' is required for supported action type '{action_type}'.",
                )
        for constraint_family in SUPPORTED_ACTIONS.get(action_type, {}).get(
            "required_constraint_families",
            []
        ):
            if constraint_family not in _constraint_families(company_data.get("constraints", [])):
                ensure_gap(
                    field=f"company.constraints.{constraint_family}",
                    category="hard_constraint",
                    verification_check="ground_required_constraint",
                    reason=(
                        f"A grounded '{constraint_family}' hard constraint is required for"
                        f" supported action type '{action_type}'."
                    ),
                )

        if not gap_map.get("action.type"):
            try:
                validate_action_payload(action)
            except (TypeError, ValueError, ValidationError) as exc:
                if isinstance(exc, ValidationError):
                    errors = exc.errors()
                else:
                    errors = [{"loc": ("action",), "msg": str(exc)}]
                for error in errors:
                    location = ".".join(str(part) for part in error["loc"] if part != "action")
                    field = f"action.{location}" if location else "action"
                    ensure_gap(
                        field=field,
                        category="action_details",
                        verification_check="formalize_action_payload",
                        reason=error["msg"],
                    )

    ordered = sorted(gap_map.values(), key=lambda gap: (_gap_priority(gap.field), gap.field))
    return ordered


def _required_action_fields(action_type: str, action: dict[str, Any]) -> list[str]:
    if action_type != "price_change":
        return list(SUPPORTED_ACTIONS[action_type]["required_action_fields"])
    if "pct_increase" in action or "scope" in action:
        return ["pct_increase", "scope"]
    if "new_unit_price" in action or "assumed_volume_multiplier" in action:
        return ["new_unit_price", "assumed_volume_multiplier"]
    return ["pct_increase", "scope"]


def _constraint_families(constraints: list[Constraint]) -> set[str]:
    families: set[str] = set()
    for constraint in constraints:
        normalized = " ".join(constraint.semi_formal.split())
        if normalized.startswith("cash_balance(t) >="):
            families.add("cash_reserve_floor")
        elif normalized.startswith("runway_months(t) = cash_balance(t)/net_burn(t) >="):
            families.add("runway_floor")
        elif normalized.startswith("initiative_budget <="):
            families.add("initiative_budget_cap")
        elif normalized.startswith("ltv_cac(channel) >="):
            families.add("ltv_cac_minimum")
        elif normalized.startswith("cumulative_units_built("):
            families.add("capacity_backlog")
        elif normalized.startswith("new_sku_contribution_margin >="):
            families.add("new_sku_margin")
        elif normalized.startswith("total_marketing_spend <="):
            families.add("marketing_spend_cap")
    return families


def _normalize_planner_gaps(
    *,
    proposal_id: str,
    gaps: list[PlannerGap],
) -> list[Stage1Gap]:
    normalized: list[Stage1Gap] = []
    seen_fields: set[str] = set()
    for gap in gaps:
        if gap.field in seen_fields:
            continue
        seen_fields.add(gap.field)
        normalized.append(
            Stage1Gap(
                id=_gap_id(proposal_id, gap.field),
                category=gap.category,
                field=gap.field,
                verification_check=gap.verification_check,
                reason=gap.reason,
            )
        )
    return normalized


def _questions_by_id(
    *,
    proposal_id: str,
    gaps: list[PlannerGap],
    questions: list[PlannerQuestion],
) -> dict[str, Stage1Question]:
    return {question.id: question for question in _questions_by_field(proposal_id=proposal_id, gaps=gaps, questions=questions).values()}


def _questions_by_field(
    *,
    proposal_id: str,
    gaps: list[PlannerGap],
    questions: list[PlannerQuestion],
) -> dict[str, Stage1Question]:
    question_map: dict[str, Stage1Question] = {}
    gaps_by_field = {gap.field: gap for gap in gaps}
    for question in questions:
        question_map[question.field] = Stage1Question(
            id=_question_id(proposal_id, question.field),
            field=question.field,
            question=question.question,
            verification_check=question.verification_check,
            rationale=question.rationale,
        )
    for field_name, gap in gaps_by_field.items():
        if field_name in question_map:
            continue
        question_map[field_name] = _fallback_question(proposal_id=proposal_id, gap=gap)
    return question_map


def _build_question_map(
    *,
    proposal_id: str,
    gaps: list[Stage1Gap],
    ai_questions: dict[str, Stage1Question],
) -> dict[str, Stage1Question]:
    result: dict[str, Stage1Question] = {}
    for gap in gaps:
        question = ai_questions.get(gap.field)
        if question is None:
            question = _fallback_question(proposal_id=proposal_id, gap=gap)
        result[question.id] = question
    return result


def _fallback_question(*, proposal_id: str, gap: Stage1Gap) -> Stage1Question:
    templates = {
        "company.name": (
            "What is the company name? I need it to emit a final battery-shaped formalization.",
            "The battery document requires an explicit company name.",
        ),
        "company.sector": (
            "What sector is the company in? I need it to emit a final battery-shaped formalization.",
            "The battery document requires an explicit company sector.",
        ),
        "objective": (
            "What exact business objective should this decision be evaluated against?",
            "Stage 1 needs a grounded objective field before formalization can complete.",
        ),
        "scope": (
            "Which supported action family best matches this proposal?",
            "Stage 1 is verifier-scoped and needs a supported action family before it can formalize.",
        ),
    }
    question_text, rationale = templates.get(
        gap.field,
        (
            f"What is the value for '{gap.field}'? I need it to unlock {gap.verification_check}.",
            gap.reason,
        ),
    )
    return Stage1Question(
        id=_question_id(proposal_id, gap.field),
        field=gap.field,
        question=question_text,
        verification_check=gap.verification_check,
        rationale=rationale,
    )


def _gap_id(proposal_id: str, field_name: str) -> str:
    return f"{proposal_id}_G_{_slug(field_name)}"


def _question_id(proposal_id: str, field_name: str) -> str:
    return f"{proposal_id}_Q_{_slug(field_name)}"


def _slug(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return lowered.strip("_") or "field"


def _gap_priority(field_name: str) -> tuple[int, str]:
    if field_name in QUESTION_PRIORITY:
        return QUESTION_PRIORITY[field_name], field_name
    if field_name.startswith("action."):
        return 10, field_name
    if field_name.startswith("company.facts."):
        return 20, field_name
    if field_name.startswith("company.constraints."):
        return 30, field_name
    return 40, field_name


def _build_battery_document(
    *,
    proposal_id: str,
    proposal_text: str,
    company_data: dict[str, Any],
    decision_data: dict[str, Any],
) -> tuple[DecisionBattery, str]:
    canonical = _canonical_battery_metadata()
    company_id = _slug(str(company_data["name"]))
    decision_id = proposal_id
    company = Company(
        id=company_id,
        name=str(company_data["name"]),
        sector=str(company_data["sector"]),
        facts=company_data["facts"],
        constraints=company_data["constraints"],
    )
    decision = Decision(
        id=decision_id,
        company=company_id,
        proposal=proposal_text,
        action=decision_data["action"],
        objective=str(decision_data["objective"]),
        stated_assumptions=decision_data["assumptions"],
    )
    battery_document = DecisionBattery(
        battery_version=canonical.battery_version,
        title=f"Stage 1 Formalization - {proposal_id}",
        note_to_candidate=canonical.note_to_candidate,
        verdict_definitions=canonical.verdict_definitions,
        schema=canonical.schema_,
        companies=[company],
        decisions=[decision],
    )
    return battery_document, decision_id


@lru_cache(maxsize=1)
def _canonical_battery_metadata() -> DecisionBattery:
    return load_battery_fixture(DEFAULT_BATTERY_PATH).fixture
