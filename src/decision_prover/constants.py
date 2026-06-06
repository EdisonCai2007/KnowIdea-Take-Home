from pathlib import Path

from .contracts.battery import BatterySchemaDescription, VerdictDefinitions

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_BATTERY_PATH = (
    PROJECT_ROOT / "codex-resources" / "original-project-specs" / "decision_battery.json"
)
DEFAULT_PROPOSALS_PATH = (
    PROJECT_ROOT / "codex-resources" / "original-project-specs" / "nl_proposals.md"
)


def canonical_battery_metadata() -> dict[str, object]:
    return {
        "battery_version": "1.0",
        "title": "Decision Prover — Evaluation Battery",
        "note_to_candidate": (
            "This file is the input to your system. For each decision, your system must emit "
            "a verdict (SUPPORTED | REFUTED | UNDECIDABLE) together with an auditable "
            "derivation, the binding constraints it checked, the load-bearing assumptions it "
            "relied on, and an attempted refutation. Do NOT hardcode to these items — we will "
            "also run held-out decisions you have not seen. All monetary values are USD. "
            "'mo' = per month."
        ),
        "verdict_definitions": VerdictDefinitions(
            SUPPORTED=(
                "There exists a valid derivation, from the stated facts and assumptions, "
                "showing the decision satisfies every hard constraint AND meets its stated "
                "objective. No hard constraint is violated under the decision's own stated "
                "assumptions."
            ),
            REFUTED=(
                "The decision provably violates at least one hard constraint, OR its negation "
                "is provable (an available alternative strictly dominates it on the stated "
                "objective), given the facts and assumptions."
            ),
            UNDECIDABLE=(
                "The verdict depends on a load-bearing assumption whose truth value is NOT "
                "pinned down by the stated facts — the decision is SUPPORTED under one reading "
                "of that assumption and REFUTED under another. The honest output names the "
                "pivotal assumption (and, ideally, the threshold at which the verdict flips) "
                "and declines to assert a proof."
            ),
            precedence_rule=(
                "A hard-constraint violation REFUTES a decision regardless of how attractive "
                "its projected returns are. Check feasibility before optimality."
            ),
        ).model_dump(mode="json"),
        "schema": BatterySchemaDescription(
            company=(
                "id, name, sector, facts{key:{value,unit,note}}, "
                "constraints[{id,kind:'hard',statement,semi_formal,note}]"
            ),
            decision=(
                "id, company, proposal(prose), action(structured), objective(what 'good' means "
                "here), stated_assumptions[{id,statement,status:'given'|'projected'}]"
            ),
            expected_output_per_decision=(
                "classification, derivation[ordered steps: {rule, inputs, result}], "
                "binding_constraints[{id, pass|fail, why}], load_bearing_assumptions[], "
                "refutation{attempted, failure_conditions}, "
                "for_UNDECIDABLE:{pivotal_assumption, flip_threshold}"
            ),
        ).model_dump(mode="json", by_alias=True),
    }
