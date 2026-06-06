from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts.output import (
    ClarificationNeededOutcome,
    OperationStatus,
    Stage1CompanyContext,
    Stage1Question,
    Stage1ReadyOutcome,
    Stage1RunRequest,
    Stage1RunResponse,
    Stage1SuggestedAnswer,
    Stage1TranscriptTurn,
    Stage1WorkingContext,
)
from .contracts.workspace import WorkspaceCompanyProfile
from .proposals import ProposalFixture
from .runtime_logging import log_event
from .settings import (
    ConfigurationError,
    DEFAULT_OPENROUTER_STAGE1_MODEL,
    OpenRouterSettings,
    get_openrouter_settings,
)

MAX_CLARIFICATION_ROUNDS = 5


class Stage1InputError(ValueError):
    """Raised when Stage 1 request inputs are invalid."""


class Stage1ExecutionError(RuntimeError):
    """Raised when the Stage 1 AI cannot produce a usable result."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InitialContextOutput(StrictModel):
    working_context: Stage1WorkingContext


class ClarificationQuestionOutput(StrictModel):
    prompt: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    suggested_answers: list[Stage1SuggestedAnswer] = Field(min_length=3, max_length=3)
    recommended_answer_index: int = Field(ge=0, le=2)


class ClarificationQuestionsOutput(StrictModel):
    questions: list[ClarificationQuestionOutput] = Field(default_factory=list, max_length=3)


class ContextUpdateOutput(StrictModel):
    working_context: Stage1WorkingContext


@dataclass(slots=True)
class _PreparedAnswer:
    question_id: str
    prompt: str
    answer: str


def canonicalize_company_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "company"


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
            proposal_id=proposal_id,
            proposal_text=proposal_lookup[proposal_id].text,
            answers=request.answers.get(proposal_id, {}),
            skip_remaining=request.skip_remaining,
            settings=settings,
            client=resolved_client,
            workspace_company=None,
        )
        for proposal_id in selected_ids
    ]
    has_pending = any(result.outcome == "clarification_needed" for result in results)
    return Stage1RunResponse(
        status=OperationStatus(
            state="stage1_pending" if has_pending else "stage1_complete",
            message=(
                "Stage 1 needs clarification answers for at least one proposal."
                if has_pending
                else "Stage 1 AI workflow complete."
            ),
        ),
        title=proposal_fixture.title,
        results=results,
    )


def run_stage1_for_workspace_proposal(
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile,
    *,
    settings: OpenRouterSettings | None = None,
    client: Any | None = None,
) -> ClarificationNeededOutcome | Stage1ReadyOutcome:
    settings, resolved_client = _resolve_client(settings=settings, client=client)
    return _start_stage1_proposal(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        settings=settings,
        client=resolved_client,
    )


def continue_stage1_for_workspace_proposal(
    result: ClarificationNeededOutcome,
    *,
    answers: dict[str, str],
    workspace_company: WorkspaceCompanyProfile,
    settings: OpenRouterSettings | None = None,
    client: Any | None = None,
) -> ClarificationNeededOutcome | Stage1ReadyOutcome:
    settings, resolved_client = _resolve_client(settings=settings, client=client)
    return _continue_stage1_proposal(
        result=result,
        answers=answers,
        workspace_company=workspace_company,
        settings=settings,
        client=resolved_client,
    )


def skip_stage1_for_workspace_proposal(
    result: ClarificationNeededOutcome,
) -> Stage1ReadyOutcome:
    transcript = list(result.transcript)
    transcript.append(
        Stage1TranscriptTurn(
            speaker="user",
            kind="continue",
            text="Continue without answering more clarification questions.",
        )
    )
    readiness_summary = "Stage 1 was marked ready at the user's request with unresolved notes carried forward."
    unresolved_notes = _dedupe_strings(
        result.working_context.what_still_matters
        + [question.rationale for question in result.questions]
    )
    transcript.append(
        Stage1TranscriptTurn(
            speaker="assistant",
            kind="ready",
            text=readiness_summary,
        )
    )
    return Stage1ReadyOutcome(
        outcome="stage1_ready",
        proposal_id=result.proposal_id,
        proposal=result.proposal,
        working_context=result.working_context,
        readiness_summary=readiness_summary,
        completion_reason="user_continue",
        unresolved_notes=unresolved_notes,
        transcript=transcript,
    )


def _resolve_client(
    *,
    settings: OpenRouterSettings | None,
    client: Any | None,
) -> tuple[OpenRouterSettings | None, Any]:
    if client is not None:
        return settings, client

    settings = settings or get_openrouter_settings(
        require_api_key=True,
        model_env_var="OPENROUTER_STAGE1_MODEL",
        default_model=DEFAULT_OPENROUTER_STAGE1_MODEL,
    )
    try:
        from .ai.client import OpenRouterClient
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ConfigurationError(
            "Stage 1 AI requires project dependencies to be installed before OpenRouter can be used."
        ) from exc
    return settings, OpenRouterClient(settings)


def _run_single_proposal(
    *,
    proposal_id: str,
    proposal_text: str,
    answers: dict[str, str],
    skip_remaining: bool,
    settings: OpenRouterSettings | None,
    client: Any,
    workspace_company: WorkspaceCompanyProfile | None,
) -> ClarificationNeededOutcome | Stage1ReadyOutcome:
    outcome = _start_stage1_proposal(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        settings=settings,
        client=client,
    )

    if answers:
        if outcome.outcome != "clarification_needed":
            raise Stage1InputError(
                f"{proposal_id}: clarification answers were provided but no questions are pending."
            )
        outcome = _continue_stage1_proposal(
            result=outcome,
            answers=answers,
            workspace_company=workspace_company,
            settings=settings,
            client=client,
        )

    if skip_remaining and outcome.outcome == "clarification_needed":
        outcome = skip_stage1_for_workspace_proposal(outcome)

    return outcome


def _start_stage1_proposal(
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile | None,
    settings: OpenRouterSettings | None,
    client: Any,
) -> ClarificationNeededOutcome | Stage1ReadyOutcome:
    log_event(
        settings=settings,
        event="stage1.start",
        payload={
            "proposal_id": proposal_id,
            "phase": "initial_context",
            "has_workspace_company": workspace_company is not None,
        },
        console_message=f"stage1.start proposal_id={proposal_id} phase=initial_context",
    )
    transcript = [
        Stage1TranscriptTurn(
            speaker="user",
            kind="proposal",
            text=proposal_text,
        )
    ]
    working_context = _build_initial_context(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        client=client,
    )
    questions = _generate_clarifications(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        working_context=working_context,
        transcript=transcript,
        client=client,
    )
    if not questions:
        return _build_stage1_ready_outcome(
            proposal_id=proposal_id,
            proposal_text=proposal_text,
            working_context=working_context,
            readiness_summary=(
                "Stage 1 is ready because no additional proof-critical clarification questions remain."
            ),
            unresolved_notes=working_context.what_still_matters,
            transcript=transcript,
            completion_reason="no_more_questions",
        )
    return _build_clarification_outcome(
        proposal_id=proposal_id,
        proposal_text=proposal_text,
        working_context=working_context,
        questions=questions,
        transcript=transcript,
    )


def _continue_stage1_proposal(
    *,
    result: ClarificationNeededOutcome,
    answers: dict[str, str],
    workspace_company: WorkspaceCompanyProfile | None,
    settings: OpenRouterSettings | None,
    client: Any,
) -> ClarificationNeededOutcome | Stage1ReadyOutcome:
    normalized_answers = _normalize_answer_map(answers)
    question_lookup = {question.id: question for question in result.questions}
    unknown_answers = sorted(set(normalized_answers) - set(question_lookup))
    if unknown_answers:
        raise Stage1InputError(
            f"{result.proposal_id}: unexpected answer keys {', '.join(unknown_answers)}."
        )

    transcript = list(result.transcript)
    prepared_answers: list[_PreparedAnswer] = []
    for question in result.questions:
        answer_text = normalized_answers.get(question.id)
        if answer_text is None:
            continue
        prepared_answers.append(
            _PreparedAnswer(
                question_id=question.id,
                prompt=question.prompt,
                answer=answer_text,
            )
        )
        transcript.append(
            Stage1TranscriptTurn(
                speaker="user",
                kind="answer",
                text=answer_text,
                question_id=question.id,
            )
        )

    working_context = _update_working_context(
        proposal_id=result.proposal_id,
        proposal_text=result.proposal,
        workspace_company=workspace_company,
        current_context=result.working_context,
        current_questions=result.questions,
        prepared_answers=prepared_answers,
        transcript=transcript,
        client=client,
    )
    current_round = _round_number_from_questions(result.questions)
    if current_round >= MAX_CLARIFICATION_ROUNDS:
        return _build_stage1_ready_outcome(
            proposal_id=result.proposal_id,
            proposal_text=result.proposal,
            working_context=working_context,
            readiness_summary=(
                f"Stage 1 stopped after the {MAX_CLARIFICATION_ROUNDS}-round clarification limit. "
                "Use the current decision brief with the unresolved notes below."
            ),
            unresolved_notes=working_context.what_still_matters,
            transcript=transcript,
            completion_reason="max_rounds",
        )
    questions = _generate_clarifications(
        proposal_id=result.proposal_id,
        proposal_text=result.proposal,
        working_context=working_context,
        transcript=transcript,
        client=client,
    )
    if not questions:
        return _build_stage1_ready_outcome(
            proposal_id=result.proposal_id,
            proposal_text=result.proposal,
            working_context=working_context,
            readiness_summary=(
                "Stage 1 is ready because no additional proof-critical clarification questions remain."
            ),
            unresolved_notes=working_context.what_still_matters,
            transcript=transcript,
            completion_reason="no_more_questions",
        )
    return _build_clarification_outcome(
        proposal_id=result.proposal_id,
        proposal_text=result.proposal,
        working_context=working_context,
        questions=questions,
        transcript=transcript,
    )


def _build_initial_context(
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile | None,
    client: Any,
) -> Stage1WorkingContext:
    payload = {
        "proposal_id": proposal_id,
        "proposal_text": proposal_text,
        "workspace_company": _workspace_payload(workspace_company),
    }
    output = _call_stage1_model(
        client=client,
        messages=[
            {"role": "system", "content": _initial_context_system_prompt()},
            {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
        ],
        response_schema=InitialContextOutput,
        error_label="initial context JSON",
    )
    return _stabilize_working_context(
        output.working_context,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
    )


def _generate_clarifications(
    *,
    proposal_id: str,
    proposal_text: str,
    working_context: Stage1WorkingContext,
    transcript: list[Stage1TranscriptTurn],
    client: Any,
) -> list[Stage1Question]:
    payload = {
        "proposal_id": proposal_id,
        "proposal_text": proposal_text,
        "working_context": working_context.model_dump(mode="json"),
        "transcript": [turn.model_dump(mode="json") for turn in transcript],
    }
    output = _call_stage1_model(
        client=client,
        messages=[
            {"role": "system", "content": _clarification_system_prompt()},
            {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
        ],
        response_schema=ClarificationQuestionsOutput,
        error_label="clarification question JSON",
    )
    round_number = _next_question_round(transcript)
    return [
        Stage1Question(
            id=_question_id(proposal_id, round_number, index),
            prompt=question.prompt,
            rationale=question.rationale,
            suggested_answers=question.suggested_answers,
            recommended_answer_index=question.recommended_answer_index,
            allow_custom_answer=True,
        )
        for index, question in enumerate(output.questions, start=1)
    ]


def _update_working_context(
    *,
    proposal_id: str,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile | None,
    current_context: Stage1WorkingContext,
    current_questions: list[Stage1Question],
    prepared_answers: list[_PreparedAnswer],
    transcript: list[Stage1TranscriptTurn],
    client: Any,
) -> Stage1WorkingContext:
    payload = {
        "proposal_id": proposal_id,
        "proposal_text": proposal_text,
        "workspace_company": _workspace_payload(workspace_company),
        "current_working_context": current_context.model_dump(mode="json"),
        "current_questions": [question.model_dump(mode="json") for question in current_questions],
        "answers": [
            {
                "question_id": answer.question_id,
                "prompt": answer.prompt,
                "answer": answer.answer,
            }
            for answer in prepared_answers
        ],
        "transcript": [turn.model_dump(mode="json") for turn in transcript],
    }
    output = _call_stage1_model(
        client=client,
        messages=[
            {"role": "system", "content": _context_update_system_prompt()},
            {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
        ],
        response_schema=ContextUpdateOutput,
        error_label="context update JSON",
    )
    return _stabilize_working_context(
        output.working_context,
        proposal_text=proposal_text,
        workspace_company=workspace_company,
        prior_company=current_context.company,
    )


def _call_stage1_model(
    *,
    client: Any,
    messages: list[dict[str, str]],
    response_schema: type[BaseModel],
    error_label: str,
) -> Any:
    try:
        completion = client.create_chat_completion(
            messages=messages,
            response_format=_build_response_format(response_schema),
        )
    except Exception as exc:  # pragma: no cover
        if exc.__class__.__name__ == "OpenRouterError":
            raise Stage1ExecutionError(str(exc)) from exc
        raise

    try:
        return response_schema.model_validate_json(completion.raw_model_response)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid JSON"
        raise Stage1ExecutionError(
            f"OpenRouter returned invalid Stage 1 {error_label}: {error_message}."
        ) from exc


def _build_response_format(schema_model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"decision_prover_{schema_model.__name__.casefold()}",
            "strict": True,
            "schema": schema_model.model_json_schema(),
        },
    }


def _build_clarification_outcome(
    *,
    proposal_id: str,
    proposal_text: str,
    working_context: Stage1WorkingContext,
    questions: list[Stage1Question],
    transcript: list[Stage1TranscriptTurn],
) -> ClarificationNeededOutcome:
    outcome_transcript = list(transcript)
    for question in questions:
        outcome_transcript.append(
            Stage1TranscriptTurn(
                speaker="assistant",
                kind="question",
                text=question.prompt,
                question_id=question.id,
            )
        )
    return ClarificationNeededOutcome(
        outcome="clarification_needed",
        proposal_id=proposal_id,
        proposal=proposal_text,
        working_context=working_context,
        questions=questions,
        transcript=outcome_transcript,
    )


def _build_stage1_ready_outcome(
    *,
    proposal_id: str,
    proposal_text: str,
    working_context: Stage1WorkingContext,
    readiness_summary: str,
    unresolved_notes: list[str],
    transcript: list[Stage1TranscriptTurn],
    completion_reason: str,
) -> Stage1ReadyOutcome:
    outcome_transcript = list(transcript)
    outcome_transcript.append(
        Stage1TranscriptTurn(
            speaker="assistant",
            kind="ready",
            text=readiness_summary,
        )
    )
    return Stage1ReadyOutcome(
        outcome="stage1_ready",
        proposal_id=proposal_id,
        proposal=proposal_text,
        working_context=working_context,
        readiness_summary=readiness_summary,
        completion_reason=completion_reason,
        unresolved_notes=_dedupe_strings(unresolved_notes),
        transcript=outcome_transcript,
    )


def _workspace_payload(workspace_company: WorkspaceCompanyProfile | None) -> dict[str, str] | None:
    if workspace_company is None:
        return None
    return {
        "name": workspace_company.name,
        "sector": workspace_company.sector,
    }


def _stabilize_working_context(
    working_context: Stage1WorkingContext,
    *,
    proposal_text: str,
    workspace_company: WorkspaceCompanyProfile | None,
    prior_company: Stage1CompanyContext | None = None,
) -> Stage1WorkingContext:
    company_name = (
        workspace_company.name
        if workspace_company is not None
        else (prior_company.name if prior_company and prior_company.name else working_context.company.name)
    )
    company_sector = (
        workspace_company.sector
        if workspace_company is not None
        else (prior_company.sector if prior_company and prior_company.sector else working_context.company.sector)
    )
    return Stage1WorkingContext(
        company=Stage1CompanyContext(name=company_name, sector=company_sector),
        proposal=proposal_text,
        decision=working_context.decision.strip(),
        objective=working_context.objective.strip(),
        what_we_know=_dedupe_strings(working_context.what_we_know),
        what_still_matters=_dedupe_strings(working_context.what_still_matters),
        constraints_mentioned=_dedupe_strings(working_context.constraints_mentioned),
        success_criteria=_dedupe_strings(working_context.success_criteria),
        notes=_dedupe_strings(working_context.notes),
    )


def _normalize_answer_map(answers: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in answers.items():
        cleaned = value.strip()
        if cleaned:
            normalized[key] = cleaned
    return normalized


def _next_question_round(transcript: list[Stage1TranscriptTurn]) -> int:
    prior_rounds = [
        _question_round_from_id(turn.question_id)
        for turn in transcript
        if turn.question_id is not None
    ]
    return (max(prior_rounds) if prior_rounds else 0) + 1


def _round_number_from_questions(questions: list[Stage1Question]) -> int:
    if not questions:
        return 0
    return _question_round_from_id(questions[0].id)


def _question_round_from_id(question_id: str | None) -> int:
    if not question_id:
        return 0
    match = re.search(r"_Q(\d+)_", question_id)
    if match is None:
        return 0
    return int(match.group(1))


def _question_id(proposal_id: str, round_number: int, index: int) -> str:
    return f"{proposal_id}_Q{round_number}_{index}"


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _initial_context_system_prompt() -> str:
    return """You are the Interviewer AI in Stage 1 of a business proposal clarification workflow.
Return JSON only. Do not wrap it in markdown.

Your job is to build a lightweight decision brief from the company context and proposal text.

Rules:
- Do not use Decision Battery structure.
- Do not classify the proposal into any hard-coded action family.
- Do not use any fixed business ontology or verifier field lists.
- State the decision in one sentence.
- State the objective in one sentence.
- Summarize what is already known, what still matters, any constraints mentioned, and what success seems to mean.
- Prefer measurable facts, thresholds, and exact stated constraints whenever the proposal already includes them.
- Extract all exact literals already present in the proposal, including prices, dates, counts, percentages, rates, capacities, deadlines, and stated thresholds.
- Preserve those exact literals verbatim in the working context.
- Put exact observed or proposed business facts in what_we_know.
- Put stated conditions, limits, and must-stay-under / must-not-exceed / must-not-drop-more-than thresholds in constraints_mentioned and success_criteria when appropriate.
- If the proposal already supplies an exact value, threshold, date, price, count, rate, or deadline, treat it as known rather than leaving it unresolved.
- Do not restate an exact threshold with a different number, stricter bound, looser bound, or normalized interpretation unless the user explicitly supplied that change.
- Do not invent baseline metrics, projected metrics, target metrics, or other exact business numbers that were not explicitly stated.
- Keep the working context concise, useful, and grounded in the user input.
- If workspace company name and sector are provided, carry them into the working context.
- The working context should be useful for future clarification rounds, not for deterministic verification.
- Do not over-infer. If something is unclear, leave it in what_still_matters instead of pretending it is known.
- Focus on the actual decision the user is making, not on general business planning.
"""


def _clarification_system_prompt() -> str:
    return """You are the Interviewer AI in Stage 1 of a business proposal clarification workflow.
Return JSON only. Do not wrap it in markdown.

Your job is to ask 1 to 3 clarification questions based on the current working context.

Rules:
- Before asking anything, silently infer any obvious labels, categories, and structure from the proposal and working context.
- Do not ask for internal labels, action types, schema fields, taxonomy, or any Decision Battery or verifier-specific structure.
- Return 1 to 3 strong questions total. Return fewer if fewer strong proof-input questions exist. Return an empty questions list if no such question remains.
- Before drafting questions, choose exactly one highest-priority proof variable family for this round and keep every question inside that family.
- A proof variable family is one tightly related proof path such as cost feasibility, revenue threshold, capacity feasibility, deadline feasibility, churn impact, margin impact, or one specific hard-constraint threshold.
- Later rounds may switch to a different variable family only after the current family is resolved, exhausted, or no longer has a strong unanswered proof-critical question.
- Ask only decision-critical questions whose answers are not already reasonably inferable and would supply an exact input for a later feasibility, threshold, constraint, or objective-impact check.
- If the proposal or working context already states an exact value, threshold, date, count, price, rate, capacity, or deadline, treat that datum as known.
- Do not ask the user to restate, confirm, refine, or choose among suggested answers for an exact datum that is already present in the proposal or working context.
- Ask only for missing exact inputs that are still needed for a later feasibility, threshold, constraint, or objective-impact check.
- Prefer the variable family that is most directly tied to the proposal's stated condition, threshold, explicit success criterion, or claimed outcome.
- Within that chosen family, prefer the exact baseline, comparison value, threshold, or pivotal missing input that would most directly determine support, refutation, or a verdict-flipping assumption.
- Prefer decision-driving questions about concrete thresholds such as cost, budget, cash, burn, revenue, margin, churn, capacity, deadline, unit volume, price, reserve floor, or another exact threshold.
- Do not ask exploratory, planning-detail, behavioral, background, marketing, positioning, demographic, location, or other flavor questions unless they are clearly decision-critical right now.
- Do not branch across multiple business areas in the same round. Do not mix cost, staffing, demand, margin, timeline, operating-model, or adjacent metric questions in one batch unless they are all part of the same single proof variable family.
- If only one strong exact-value question exists in the chosen family, return one question rather than branching to fill the batch.
- Each question must include exactly 3 suggested answers, and the user must still be free to type a custom answer.
- Suggested answers must be concrete, directly responsive, and must be exact literal values with units, dates, counts, percentages, rates, capacities, thresholds, or another similarly exact measurable input.
- Do not use generic suggestions like 'best estimate', 'specific answer', or 'unknown for now'.
- Do not use approximate or inequality phrasing in suggested answers, including 'about', 'around', 'roughly', 'less than', 'more than', 'at least', or 'up to'.
- Do not use ranges in suggested answers.
- Do not use categorical suggested answers. If a potentially useful question cannot be expressed with exact-value suggested answers, skip that question instead of emitting categorical or approximate options.
- Before returning, remove any question that is soft, redundant, schema-filling, or not directly usable in later reasoning.
"""


def _context_update_system_prompt() -> str:
    return """You are the Context Updater AI in Stage 1 of a business proposal clarification workflow.
Return JSON only. Do not wrap it in markdown.

Your job is to update the current working context using the user's raw clarification answers.

Rules:
- Do not use Decision Battery structure.
- Do not force the proposal into any hard-coded action taxonomy.
- Preserve prior context unless the new answers clearly change or refine it.
- You may refine the decision understanding, but do not replace the core decision unless the user clearly corrected it.
- Treat the user's answer strings as the source of truth for what changed.
- Update the decision, objective, what we know, what still matters, constraints mentioned, success criteria, and notes so the next AI step has a better context.
- Keep the brief stable and compact.
- Preserve the current proof path focus unless the new answer clearly resolves it or makes a different unresolved variable family more important.
- Remove an item from what_still_matters only if the user answer actually resolves it.
- Sharpen the brief with exact quantities, thresholds, and units when the user provides them.
- Do not invent uplift assumptions, percentages, demand effects, or other projected impacts unless the user explicitly supplied them.
"""
