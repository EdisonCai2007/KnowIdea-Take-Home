from __future__ import annotations

from ..ai.service import generate_ai_explanation
from ..contracts.context import DecisionContext
from ..contracts.output import VerificationExplainResponse
from ..settings import OpenRouterSettings, get_openrouter_settings
from .core import verify_decision


def explain_verification(
    context: DecisionContext,
    *,
    settings: OpenRouterSettings | None = None,
) -> VerificationExplainResponse:
    result = verify_decision(context)
    resolved_settings = settings or get_openrouter_settings(require_api_key=True)
    return generate_ai_explanation(context, result, settings=resolved_settings)
