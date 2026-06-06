from __future__ import annotations

from ..ai.service import generate_ai_explanation
from ..contracts.context import DecisionContext
from ..contracts.output import VerificationExplainResponse
from ..runtime_logging import log_event
from ..settings import ConfigurationError, OpenRouterSettings, get_openrouter_settings
from .core import verify_decision


def explain_verification(
    context: DecisionContext,
    *,
    settings: OpenRouterSettings | None = None,
) -> VerificationExplainResponse:
    result = verify_decision(context)
    resolved_settings = settings or get_openrouter_settings(require_api_key=False)
    log_event(
        settings=resolved_settings,
        event="explain.start",
        payload={
            "decision_id": context.id,
            "verified_classification": result.classification.value,
        },
        console_message=f"explain.start decision_id={context.id}",
    )
    if resolved_settings.api_key is None:
        log_event(
            settings=resolved_settings,
            event="explain.result",
            payload={
                "decision_id": context.id,
                "error": "missing_openrouter_api_key",
                "status": "configuration_error",
            },
            console_message=f"explain.result decision_id={context.id} status=configuration_error",
        )
        raise ConfigurationError(
            "OPENROUTER_API_KEY is required for AI explanation surfaces. Add it to .env or"
            " the process environment."
        )

    response = generate_ai_explanation(context, result, settings=resolved_settings)
    log_event(
        settings=resolved_settings,
        event="explain.result",
        payload={
            "comparison": response.comparison,
            "decision_id": context.id,
            "message": response.message,
            "status": response.ai_status,
        },
        console_message=(
            f"explain.result decision_id={context.id} "
            f"status={response.ai_status} comparison={response.comparison}"
        ),
    )
    return response
