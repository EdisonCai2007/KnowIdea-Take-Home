from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from decision_prover.contracts.battery import (
    BatterySchemaDescription,
    Company,
    Decision,
    DecisionBattery,
    StatedAssumption,
    VerdictDefinitions,
)
from decision_prover.contracts.output import (
    BindingConstraintResult,
    ClarificationNeededOutcome,
    DerivationStep,
    GroundingEntry,
    GroundingReport,
    OperationStatus,
    RefutationResult,
    Stage1CompanyContext,
    Stage1Question,
    Stage1ReadyOutcome,
    Stage1SuggestedAnswer,
    Stage1WorkingContext,
    VerificationResult,
)
from decision_prover.settings import ConfigurationError
from decision_prover.web import create_app


def _working_context() -> Stage1WorkingContext:
    return Stage1WorkingContext(
        company=Stage1CompanyContext(name="Northwind Software", sector="B2B SaaS"),
        proposal="We want to raise our prices by 20% to increase revenue.",
        decision="Raise prices by 20% for new customers only.",
        objective="Increase revenue while monitoring conversion quality.",
        what_we_know=["The proposal mentions a 20% price increase."],
        what_still_matters=["Which customers are affected."],
        constraints_mentioned=[],
        success_criteria=["Higher revenue from new customers."],
        notes=[],
    )


def _clarification_result(proposal_id: str, proposal_text: str) -> ClarificationNeededOutcome:
    return ClarificationNeededOutcome(
        outcome="clarification_needed",
        proposal_id=proposal_id,
        proposal=proposal_text,
        working_context=_working_context(),
        questions=[
            Stage1Question(
                id=f"{proposal_id}_Q1_1",
                prompt="Who exactly would this price change apply to?",
                rationale="I need the affected customer scope to tighten the decision brief.",
                suggested_answers=[
                    Stage1SuggestedAnswer(label="All customers", value="all customers"),
                    Stage1SuggestedAnswer(label="New customers only", value="new customers only"),
                    Stage1SuggestedAnswer(
                        label="Existing customers only",
                        value="existing customers only",
                    ),
                ],
                recommended_answer_index=1,
            )
        ],
        transcript=[],
    )


def _ready_result(proposal_id: str, proposal_text: str) -> Stage1ReadyOutcome:
    context = _working_context().model_copy(
        update={
            "what_we_know": [
                "The proposal mentions a 20% price increase.",
                "The price change applies to new customers only.",
            ],
            "what_still_matters": [],
        }
    )
    return Stage1ReadyOutcome(
        outcome="stage1_ready",
        proposal_id=proposal_id,
        proposal=proposal_text,
        working_context=context,
        readiness_summary="Stage 1 is ready because no additional proof-critical clarification questions remain.",
        completion_reason="no_more_questions",
        unresolved_notes=[],
        transcript=[],
    )


def _battery_document(proposal_id: str, proposal_text: str) -> DecisionBattery:
    return DecisionBattery(
        battery_version="1.0",
        title="Decision Prover — Evaluation Battery",
        note_to_candidate="note",
        verdict_definitions=VerdictDefinitions(
            SUPPORTED="supported",
            REFUTED="refuted",
            UNDECIDABLE="undecidable",
            precedence_rule="hard constraints first",
        ),
        schema_=BatterySchemaDescription(
            company="company",
            decision="decision",
            expected_output_per_decision="output",
        ),
        companies=[
            Company(
                id="northwind-software",
                name="Northwind Software",
                sector="B2B SaaS",
                facts={},
                constraints=[],
            )
        ],
        decisions=[
            Decision(
                id=proposal_id,
                company="northwind-software",
                proposal=proposal_text,
                action={"type": "price_change", "pct_increase": 0.2, "scope": "new_customers_only"},
                objective="Increase revenue while monitoring conversion quality.",
                stated_assumptions=[
                    StatedAssumption(
                        id="A1",
                        statement="Conversion impact is not yet measured for the price change.",
                        status="given",
                    )
                ],
            )
        ],
    )


def _formalization_success(proposal_id: str, proposal_text: str):
    from decision_prover.contracts.output import (
        NormalizedAction,
        NormalizedFeasibilityBundle,
        Stage2FormalizationSuccess,
    )

    return Stage2FormalizationSuccess(
        status="formalized",
        normalized_bundle=NormalizedFeasibilityBundle(
            action=NormalizedAction(
                statement="Raise prices by 20% for new customers only.",
                type="price_change",
                parameters={"pct_increase": 0.2, "scope": "new_customers_only"},
            ),
            facts=[],
            gating_conditions=[],
            assumptions=[],
            unknowns=[],
            notes=[],
        ),
        battery_document=_battery_document(proposal_id, proposal_text),
        primary_decision_id=proposal_id,
        grounding_report=GroundingReport(
            entries=[
                GroundingEntry(
                    field="decisions[0].action.scope",
                    source_type="answer",
                    source_quote="new customers only",
                    source_locator=f"{proposal_id}_Q1_1",
                )
            ]
        ),
        notes=[],
    )


def _formalization_error():
    from decision_prover.contracts.output import Stage2FormalizationError

    return Stage2FormalizationError(
        status="formalization_error",
        message="OpenRouter returned invalid Stage 2 formalization JSON.",
        grounding_report=None,
        notes=[],
    )


def _verification_result() -> VerificationResult:
    return VerificationResult(
        classification="UNDECIDABLE",
        derivation=[DerivationStep(rule="missing_verifier_inputs", inputs={}, result="missing proof input(s): action.scope")],
        binding_constraints=[BindingConstraintResult(id="C1", passed=True, why="No hard-constraint violation was formalized.")],
        load_bearing_assumptions=[],
        refutation=RefutationResult(attempted=True, failure_conditions="missing proof input(s): action.scope"),
        pivotal_assumption="Required proof inputs are missing from the formalized decision.",
        flip_threshold="Provide the missing input(s) so the verifier can compute the verdict boundary.",
        supported_if="the missing inputs satisfy every applicable constraint and objective check",
        refuted_if="the missing inputs violate an applicable constraint or objective check",
    )


def _stage1_response(results: list[dict]) -> dict:
    return {
        "status": {
            "state": "stage1_complete",
            "message": "Stage 1 AI workflow complete.",
        },
        "title": "Natural-Language Proposals",
        "results": results,
    }


def test_web_health_and_data_endpoints(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.web.app.build_stage1_run_response",
        lambda proposal_fixture, request=None: _stage1_response(
            [
                {
                    "outcome": "clarification_needed",
                    "proposal_id": "P5",
                    "proposal": "We want to raise our prices by 20%.",
                    "working_context": _working_context().model_dump(mode="json"),
                    "questions": [
                        {
                            "id": "P5_Q1_1",
                            "prompt": "Who exactly would this price change apply to?",
                            "rationale": "I need the affected customer scope to tighten the decision brief.",
                            "suggested_answers": [
                                {"label": "All customers", "value": "all customers"},
                                {"label": "New customers only", "value": "new customers only"},
                                {"label": "Existing customers only", "value": "existing customers only"},
                            ],
                            "recommended_answer_index": 1,
                            "allow_custom_answer": True,
                        }
                    ],
                    "transcript": [],
                }
            ]
        ),
    )

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/stage1").status_code == 200
    assert client.get("/api/stage1").json()["results"][0]["working_context"]["objective"] == _working_context().objective
    assert client.get("/api/battery").status_code == 200
    assert client.get("/api/verify/D2").status_code == 200
    assert client.get("/api/proposals").status_code == 200


def test_web_stage1_returns_503_for_missing_openrouter_configuration(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    def _broken_stage1(proposal_fixture, request=None):
        raise ConfigurationError("OPENROUTER_API_KEY is required for Stage 1 AI.")

    monkeypatch.setattr("decision_prover.web.app.build_stage1_run_response", _broken_stage1)

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.get("/api/stage1")
    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is required for Stage 1 AI."


def test_web_workspace_auto_formalizes_after_answers_and_skip(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "decision_prover.web.app.build_workspace_stage1_result",
        lambda proposal_id, proposal_text, workspace_company: _clarification_result(
            proposal_id,
            proposal_text,
        ),
    )
    monkeypatch.setattr(
        "decision_prover.web.app.continue_workspace_stage1_result",
        lambda result, answers, workspace_company: _ready_result(
            result.proposal_id,
            result.proposal,
        ),
    )
    monkeypatch.setattr(
        "decision_prover.web.app.skip_workspace_stage1_result",
        lambda result: _ready_result(result.proposal_id, result.proposal),
    )
    monkeypatch.setattr(
        "decision_prover.web.app.build_workspace_stage2_handoff",
        lambda result, workspace_company, answers: (
            _formalization_success(result.proposal_id, result.proposal),
            _verification_result(),
        ),
    )

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    client.put(
        "/api/workspace",
        json={"name": "Northwind Software", "sector": "B2B SaaS", "description": None},
    )

    proposal_text = "We want to raise our prices by 20% to increase revenue."
    start_response = client.post("/api/workspace/proposal", json={"proposal": proposal_text})
    assert start_response.status_code == 200
    assert start_response.json()["active_session"]["result"]["outcome"] == "clarification_needed"
    assert start_response.json()["active_session"]["formalization"] is None

    answer_response = client.post(
        "/api/workspace/proposal/answers",
        json={"answers": {"WP1_Q1_1": "new customers only"}},
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["active_session"]["result"]["outcome"] == "stage1_ready"
    assert answer_response.json()["active_session"]["formalization"]["status"] == "formalized"
    assert answer_response.json()["active_session"]["verification_result"]["classification"] == "UNDECIDABLE"

    ready_view = client.get("/")
    assert ready_view.status_code == 200
    assert "Stage 2 Verdict" in ready_view.text
    assert "Formalized Battery Document" in ready_view.text
    assert "Grounding Report" in ready_view.text

    reset_response = client.delete("/api/workspace/proposal")
    assert reset_response.status_code == 200
    assert reset_response.json()["active_session"] is None

    client.post("/api/workspace/proposal", json={"proposal": proposal_text})
    skip_response = client.post("/api/workspace/proposal/skip")
    assert skip_response.status_code == 200
    assert skip_response.json()["active_session"]["result"]["outcome"] == "stage1_ready"
    assert skip_response.json()["active_session"]["formalization"]["status"] == "formalized"


def test_web_workspace_stores_formalization_error_and_retries(
    battery_path: Path,
    proposals_path: Path,
    monkeypatch,
) -> None:
    call_count = {"formalize": 0}

    monkeypatch.setattr(
        "decision_prover.web.app.build_workspace_stage1_result",
        lambda proposal_id, proposal_text, workspace_company: _ready_result(
            proposal_id,
            proposal_text,
        ),
    )

    def _fake_handoff(result, workspace_company, answers):
        call_count["formalize"] += 1
        if call_count["formalize"] == 1:
            return _formalization_error(), None
        return _formalization_success(result.proposal_id, result.proposal), _verification_result()

    monkeypatch.setattr("decision_prover.web.app.build_workspace_stage2_handoff", _fake_handoff)

    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    client.put(
        "/api/workspace",
        json={"name": "Northwind Software", "sector": "B2B SaaS", "description": None},
    )

    proposal_text = "We want to raise our prices by 20% to increase revenue."
    start_response = client.post("/api/workspace/proposal", json={"proposal": proposal_text})
    assert start_response.status_code == 200
    assert start_response.json()["active_session"]["formalization"]["status"] == "formalization_error"
    assert start_response.json()["active_session"]["verification_result"] is None

    retry_response = client.post("/api/workspace/proposal/formalize")
    assert retry_response.status_code == 200
    assert retry_response.json()["active_session"]["formalization"]["status"] == "formalized"
    assert retry_response.json()["active_session"]["verification_result"]["classification"] == "UNDECIDABLE"
    assert call_count["formalize"] == 2


def test_web_workspace_validation_rejects_blank_required_fields(
    battery_path: Path,
    proposals_path: Path,
) -> None:
    app = create_app(battery_input=battery_path, proposal_input=proposals_path)
    client = TestClient(app)

    response = client.put(
        "/api/workspace",
        json={"name": "   ", "sector": "   ", "description": "Optional copy"},
    )
    assert response.status_code == 422
    assert "must not be blank" in response.text
