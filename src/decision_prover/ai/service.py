from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ..contracts.context import DecisionContext
from ..contracts.output import (
    AiIndependentResult,
    ExplainDiagnostics,
    VerificationExplainResponse,
    VerificationResult,
)
from ..settings import OpenRouterSettings
from .client import OpenRouterClient, OpenRouterCompletion, OpenRouterError

SYSTEM_PROMPT = """You independently classify already-formalized business decisions.
Return JSON only. Do not wrap it in markdown.
You will receive a normalized decision context only, not the code verdict.
Classify the decision as exactly one of SUPPORTED, REFUTED, or UNDECIDABLE.
SUPPORTED means the stated facts and assumptions are sufficient to show the action satisfies every hard constraint and meets its stated objective.
REFUTED means the action provably violates a hard constraint, or its negation is provable on the stated objective.
UNDECIDABLE means the verdict depends on a load-bearing assumption or missing threshold the provided facts do not pin down.
Evaluate contradictions and hard-constraint failures first.
If any hard constraint is provably violated from the given facts, return REFUTED.
If the decision is provably dominated or its objective is provably defeated on the stated facts, return REFUTED.
Only return UNDECIDABLE when no hard-constraint violation or contradiction is provable and the outcome still turns on a missing or load-bearing assumption.
Do not default to UNDECIDABLE when the provided facts already support a contradiction or hard failure.
Hard-constraint violations take precedence over upside.
Make your own decision from the supplied decision context. Do not say you agree with code or reference any hidden verifier result.
Return the requested JSON shape with a short summary and concise notes.
"""


def generate_ai_explanation(
    context: DecisionContext,
    result: VerificationResult,
    *,
    settings: OpenRouterSettings,
    client: OpenRouterClient | None = None,
) -> VerificationExplainResponse:
    client = client or OpenRouterClient(settings)

    try:
        completion = client.create_chat_completion(
            messages=_build_messages(context=context),
            response_format=_build_response_format(),
        )
    except OpenRouterError as exc:
        return VerificationExplainResponse(
            result=result,
            ai_status="error",
            comparison="ai_error",
            model=settings.model,
            ai_result=None,
            message=str(exc),
            diagnostics=_build_error_diagnostics(exc=exc),
        )

    try:
        ai_result = AiIndependentResult.model_validate_json(completion.raw_model_response)
    except ValidationError as exc:
        error_message = exc.errors()[0]["msg"] if exc.errors() else "invalid AI verdict JSON"
        return VerificationExplainResponse(
            result=result,
            ai_status="error",
            comparison="ai_error",
            model=settings.model,
            ai_result=None,
            message=f"OpenRouter returned invalid AI verdict JSON: {error_message}.",
            diagnostics=_build_completion_diagnostics(
                stage="parse",
                completion=completion,
                parsed_ai_result=None,
            ),
        )

    return VerificationExplainResponse(
        result=result,
        ai_status="generated",
        comparison=_build_comparison(result=result, ai_result=ai_result),
        model=settings.model,
        ai_result=ai_result,
        message=None,
        diagnostics=_build_completion_diagnostics(
            stage="success",
            completion=completion,
            parsed_ai_result=ai_result,
        ),
    )


def _build_messages(
    *,
    context: DecisionContext,
) -> list[dict[str, str]]:
    payload = {
        "decision_context": context.model_dump(mode="json", by_alias=True),
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, indent=2, sort_keys=True)},
    ]


def _build_completion_diagnostics(
    *,
    stage: str,
    completion: OpenRouterCompletion,
    parsed_ai_result: AiIndependentResult | None,
) -> ExplainDiagnostics:
    return ExplainDiagnostics(
        stage=stage,
        provider_response_json=_sanitize_provider_response_json(completion.provider_response_json),
        response_id=completion.response_id,
        response_model=completion.response_model,
        provider=completion.provider,
        system_fingerprint=completion.system_fingerprint,
        finish_reason=completion.finish_reason,
        native_finish_reason=completion.native_finish_reason,
        usage=completion.usage,
        openrouter_metadata=completion.openrouter_metadata,
        http_status=completion.http_status,
        parsed_ai_result=parsed_ai_result,
    )


def _build_error_diagnostics(
    *,
    exc: OpenRouterError,
) -> ExplainDiagnostics:
    return ExplainDiagnostics(
        stage="provider",
        provider_response_json=_sanitize_provider_response_json(exc.provider_response_json),
        response_id=exc.response_id,
        response_model=exc.response_model,
        provider=exc.provider,
        system_fingerprint=exc.system_fingerprint,
        finish_reason=exc.finish_reason,
        native_finish_reason=exc.native_finish_reason,
        usage=exc.usage,
        openrouter_metadata=exc.openrouter_metadata,
        http_status=exc.http_status,
        parsed_ai_result=None,
    )


def _build_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "decision_prover_ai_verdict",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "classification": {
                        "type": "string",
                        "enum": ["SUPPORTED", "REFUTED", "UNDECIDABLE"],
                    },
                    "summary": {"type": "string", "minLength": 1},
                    "notes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string", "minLength": 1},
                                "note": {"type": "string", "minLength": 1},
                            },
                            "required": ["topic", "note"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "classification",
                    "summary",
                    "notes",
                ],
                "additionalProperties": False,
            },
        },
    }


def _build_comparison(
    *,
    result: VerificationResult,
    ai_result: AiIndependentResult,
) -> str:
    if ai_result.classification == result.classification:
        return "match"
    return "mismatch"


def _sanitize_provider_response_json(
    provider_response_json: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if provider_response_json is None:
        return None

    sanitized = json.loads(json.dumps(provider_response_json))
    choices = sanitized.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict) and "content" in message:
                message["content"] = "[omitted]"
            if isinstance(choice.get("text"), str):
                choice["text"] = "[omitted]"
    return sanitized
