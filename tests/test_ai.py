import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import decision_prover.ai.service as ai_service
import decision_prover.settings as settings_module
from decision_prover.ai.client import OpenRouterCompletion, OpenRouterError
from decision_prover.ai.service import generate_ai_explanation
from decision_prover.cli import app
from decision_prover.fixtures import get_decision_context, load_battery_fixture
from decision_prover.settings import (
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_MODEL,
    OpenRouterSettings,
)
from decision_prover.verifier import verify_decision
from decision_prover.web import create_app

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

runner = CliRunner()


class FakeClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> OpenRouterCompletion:
        assert messages
        assert response_format["type"] == "json_schema"
        return _completion(self.payload)


class SuccessfulOpenRouterClient:
    def __init__(self, settings: OpenRouterSettings) -> None:
        self.settings = settings

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> OpenRouterCompletion:
        assert messages
        assert response_format["type"] == "json_schema"
        payload = json.dumps(
            {
                "classification": "UNDECIDABLE",
                "summary": "The facts do not quantify the objective tightly enough to prove the hire either way.",
                "notes": [
                    {
                        "topic": "objective",
                        "note": "Product-velocity improvement is material to the verdict but not quantified.",
                    }
                ],
            }
        )
        return _completion(payload)


class ErroringOpenRouterClient:
    def __init__(self, settings: OpenRouterSettings) -> None:
        self.settings = settings

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> OpenRouterCompletion:
        raise OpenRouterError(
            "Structured output request failed.",
            raw_provider_response='{"error":"structured output request failed"}',
            provider_response_json={"error": "structured output request failed"},
            http_status=400,
        )


class InspectingPromptClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, object],
    ) -> OpenRouterCompletion:
        assert messages
        assert response_format["type"] == "json_schema"
        assert "verification_result" not in messages[-1]["content"]
        assert "decision_context" in messages[-1]["content"]
        return _completion(self.payload)


def _context(battery_path: Path, decision_id: str):
    loaded = load_battery_fixture(battery_path)
    return get_decision_context(loaded, decision_id).model_copy(deep=True)


def _settings() -> OpenRouterSettings:
    return OpenRouterSettings(
        api_key="test-key",
        model=DEFAULT_OPENROUTER_MODEL,
        base_url=DEFAULT_OPENROUTER_BASE_URL,
        timeout_seconds=30.0,
    )


def _completion(payload: str) -> OpenRouterCompletion:
    provider_response_json = {
        "id": "gen-test-1",
        "model": DEFAULT_OPENROUTER_MODEL,
        "provider": "OpenRouter",
        "system_fingerprint": "fp-test",
        "choices": [
            {
                "finish_reason": "stop",
                "native_finish_reason": "STOP",
                "message": {
                    "role": "assistant",
                    "content": payload,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        "openrouter_metadata": {
            "request_id": "req-test-1",
        },
    }
    return OpenRouterCompletion(
        raw_provider_response=json.dumps(provider_response_json),
        provider_response_json=provider_response_json,
        raw_model_response=payload,
        response_id="gen-test-1",
        response_model=DEFAULT_OPENROUTER_MODEL,
        provider="OpenRouter",
        system_fingerprint="fp-test",
        finish_reason="stop",
        native_finish_reason="STOP",
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        openrouter_metadata={"request_id": "req-test-1"},
        http_status=200,
    )


def test_settings_load_dotenv_and_default_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "OPENROUTER_API_KEY=dotenv-key",
                "OPENROUTER_BASE_URL=https://example.com/api/v1",
                "OPENROUTER_TIMEOUT_SECONDS=12.5",
            ]
        )
    )
    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_TIMEOUT_SECONDS", raising=False)

    resolved = settings_module.get_openrouter_settings(require_api_key=True)

    assert resolved.api_key == "dotenv-key"
    assert resolved.model == DEFAULT_OPENROUTER_MODEL
    assert resolved.base_url == "https://example.com/api/v1"
    assert resolved.timeout_seconds == 12.5


def test_verify_explain_cli_requires_api_key(
    battery_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = runner.invoke(
        app,
        ["verify", "explain", "--input", str(battery_path), "--decision-id", "D1"],
    )

    assert result.exit_code == 1
    assert "OPENROUTER_API_KEY" in result.output


def test_verify_explain_cli_returns_generated_payload(
    battery_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenRouterClient", SuccessfulOpenRouterClient)

    result = runner.invoke(
        app,
        ["verify", "explain", "--input", str(battery_path), "--decision-id", "D1"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ai_status"] == "generated"
    assert payload["comparison"] == "match"
    assert payload["model"] == DEFAULT_OPENROUTER_MODEL
    assert payload["result"]["classification"] == "UNDECIDABLE"
    assert payload["ai_result"]["classification"] == "UNDECIDABLE"
    assert payload["diagnostics"]["finish_reason"] == "stop"


def test_verification_explain_endpoint_requires_api_key(
    battery_path: Path,
    proposals_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    app_instance = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app_instance)

    response = client.get("/api/verify/D1/explain")

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_verification_explain_endpoint_returns_generated_payload(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenRouterClient", SuccessfulOpenRouterClient)

    app_instance = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app_instance)

    response = client.get("/api/verify/D1/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_status"] == "generated"
    assert payload["comparison"] == "match"
    assert payload["result"]["classification"] == "UNDECIDABLE"
    assert payload["ai_result"]["classification"] == "UNDECIDABLE"
    assert payload["diagnostics"]["finish_reason"] == "stop"


def test_generate_ai_explanation_returns_generated_for_matching_independent_verdict(
    battery_path: Path,
) -> None:
    context = _context(battery_path, "D2")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient(
            json.dumps(
                {
                    "classification": "SUPPORTED",
                    "summary": "The channel test fits the stated objective while preserving the hard constraints.",
                    "notes": [
                        {
                            "topic": "constraints",
                            "note": "The spend, reserve, runway, and LTV/CAC checks all appear satisfied.",
                        },
                        {
                            "topic": "assumptions",
                            "note": "The verdict still relies on the projected CAC and cohort-behavior assumptions.",
                        },
                    ],
                }
            )
        ),
    )

    assert response.ai_status == "generated"
    assert response.comparison == "match"
    assert response.ai_result is not None
    assert response.ai_result.classification == result.classification
    assert response.ai_result.summary.startswith("The channel test")
    assert len(response.ai_result.notes) == 2
    assert response.message is None
    assert response.diagnostics is not None
    assert response.diagnostics.stage == "success"
    assert response.diagnostics.finish_reason == "stop"
    assert response.diagnostics.provider_response_json is not None
    assert response.diagnostics.provider_response_json["choices"][0]["message"]["content"] == "[omitted]"
    assert response.diagnostics.parsed_ai_result is not None


def test_generate_ai_explanation_returns_generated_for_mismatching_independent_verdict(
    battery_path: Path,
) -> None:
    context = _context(battery_path, "D2")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient(
            json.dumps(
                {
                    "classification": "REFUTED",
                    "summary": "This AI second opinion sees the initiative as too assumption-sensitive to support.",
                    "notes": [
                        {
                            "topic": "objective",
                            "note": "The objective may not be satisfied under the projected acquisition assumptions.",
                        }
                    ],
                }
            )
        ),
    )

    assert response.ai_status == "generated"
    assert response.comparison == "mismatch"
    assert response.ai_result is not None
    assert response.ai_result.classification != result.classification
    assert response.message is None
    assert response.diagnostics is not None
    assert response.diagnostics.stage == "success"
    assert response.diagnostics.parsed_ai_result is not None


def test_generate_ai_explanation_uses_decision_context_only_for_prompt(battery_path: Path) -> None:
    context = _context(battery_path, "D1")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=InspectingPromptClient(
            json.dumps(
                {
                    "classification": "UNDECIDABLE",
                    "summary": "The facts do not pin down the objective impact tightly enough.",
                    "notes": [
                        {
                            "topic": "objective",
                            "note": "Velocity impact is the unresolved pivot.",
                        }
                    ],
                }
            )
        ),
    )

    assert response.ai_status == "generated"
    assert response.comparison == "match"
    assert response.ai_result is not None
    assert response.ai_result.classification == result.classification


def test_generate_ai_explanation_accepts_display_only_notes(battery_path: Path) -> None:
    context = _context(battery_path, "D1")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient(
            json.dumps(
                {
                    "classification": "UNDECIDABLE",
                    "summary": "The AI rounds figures like 6.6207 to 6.62 in prose and still returns valid output.",
                    "notes": [
                        {
                            "topic": "runway",
                            "note": "Runway looks a bit above 6.62 months after the hire in this informal summary.",
                        },
                        {
                            "topic": "cost",
                            "note": "The plan informally describes the hiring cost as about 200k per engineer.",
                        },
                    ],
                }
            )
        ),
    )

    assert response.ai_status == "generated"
    assert response.comparison == "match"
    assert response.ai_result is not None
    assert response.ai_result.summary.startswith("The AI rounds figures")
    assert len(response.ai_result.notes) == 2


def test_generate_ai_explanation_returns_error_for_non_json_response(battery_path: Path) -> None:
    context = _context(battery_path, "D2")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient("not json"),
    )

    assert response.ai_status == "error"
    assert response.comparison == "ai_error"
    assert response.ai_result is None
    assert response.message is not None
    assert "invalid AI verdict JSON" in response.message
    assert response.diagnostics is not None
    assert response.diagnostics.stage == "parse"
    assert response.diagnostics.parsed_ai_result is None
    assert response.diagnostics.provider_response_json is not None
    assert response.diagnostics.provider_response_json["choices"][0]["message"]["content"] == "[omitted]"


def test_generate_ai_explanation_returns_error_for_schema_invalid_json(battery_path: Path) -> None:
    context = _context(battery_path, "D2")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient(
            json.dumps(
                {
                    "classification": "SUPPORTED",
                    "summary": "Checked independent verdict.",
                    "notes": {},
                }
            )
        ),
    )

    assert response.ai_status == "error"
    assert response.comparison == "ai_error"
    assert response.ai_result is None
    assert response.message is not None
    assert "invalid AI verdict JSON" in response.message
    assert response.diagnostics is not None
    assert response.diagnostics.stage == "parse"
    assert response.diagnostics.parsed_ai_result is None
    assert response.diagnostics.provider_response_json is not None
    assert response.diagnostics.provider_response_json["choices"][0]["message"]["content"] == "[omitted]"


def test_generate_ai_explanation_returns_error_for_provider_schema_failure(
    battery_path: Path,
) -> None:
    context = _context(battery_path, "D2")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=ErroringOpenRouterClient(_settings()),
    )

    assert response.ai_status == "error"
    assert response.comparison == "ai_error"
    assert response.ai_result is None
    assert response.message == "Structured output request failed."
    assert response.diagnostics is not None
    assert response.diagnostics.stage == "provider"
    assert response.diagnostics.parsed_ai_result is None
    assert response.diagnostics.provider_response_json == {"error": "structured output request failed"}
    assert response.diagnostics.http_status == 400


def test_generate_ai_explanation_no_longer_returns_annotation_artifact_shape(
    battery_path: Path,
) -> None:
    context = _context(battery_path, "D1")
    result = verify_decision(context)

    response = generate_ai_explanation(
        context,
        result,
        settings=_settings(),
        client=FakeClient(
            json.dumps(
                {
                    "classification": "UNDECIDABLE",
                    "summary": "Independent AI verdict returned.",
                    "notes": [
                        {
                            "topic": "difference",
                            "note": "This confirms the explain surface now carries AI verdict data instead of annotation sections.",
                        }
                    ],
                }
            )
        ),
    )

    payload = response.model_dump(mode="json", by_alias=True)

    assert response.ai_status == "generated"
    assert response.ai_result is not None
    assert "ai_result" in payload
    assert "artifact" not in payload
    assert "parsed_ai_result" in payload["diagnostics"]
    assert "parsed_artifact" not in payload["diagnostics"]
    assert "raw_model_response" not in payload["diagnostics"]
    assert "raw_provider_response" not in payload["diagnostics"]


def test_explain_mode_preserves_verified_result_for_full_battery(battery_path: Path) -> None:
    loaded = load_battery_fixture(battery_path)
    payload = json.dumps(
        {
            "classification": "UNDECIDABLE",
            "summary": "Independent AI verdict payload.",
            "notes": [
                {
                    "topic": "general",
                    "note": "This fixed mock payload is enough to confirm the deterministic verifier result is preserved.",
                }
            ],
        }
    )

    for context in loaded.decision_contexts:
        result = verify_decision(context)
        response = generate_ai_explanation(
            context,
            result,
            settings=_settings(),
            client=FakeClient(payload),
        )

        assert response.ai_status == "generated"
        assert response.comparison in {"match", "mismatch"}
        assert response.result.model_dump(mode="json", by_alias=True) == result.model_dump(
            mode="json",
            by_alias=True,
        )
