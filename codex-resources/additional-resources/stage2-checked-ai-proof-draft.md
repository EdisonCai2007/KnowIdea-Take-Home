# Stage 2 Checked AI Proof Draft

Date: June 6, 2026
Status: Draft

## Purpose

This document defines a Stage 2 direction that uses:

- Stage 1 output as the canonical input
- AI to propose a structured proof draft
- code to validate grounding, arithmetic, and comparison execution

The goal is to avoid both extremes:

- a brittle hand-coded verifier that only works for a few narrow scenarios
- an unconstrained AI verifier that sounds rigorous but cannot be audited

## Core Position

Stage 2 should not begin by translating workspace proposals into full battery JSON.

Stage 2 should also not try to solve every business decision with a giant manual checker library.

Instead, Stage 2 should:

1. read the grounded Stage 1 brief
2. ask AI to propose a proof draft in a small allowed structure
3. have code re-check every accepted proof step
4. return `SUPPORTED`, `REFUTED`, or `UNDECIDABLE` based on what was actually checkable

This makes AI responsible for interpretation and proof proposal, while code remains responsible for enforcement.

## Canonical Input

For workspace proposals, the canonical Stage 2 input should be the `stage1_ready` result:

- proposal
- decision
- objective
- what_we_know
- constraints_mentioned
- success_criteria
- what_still_matters
- unresolved_notes
- transcript
- clarification answers already captured in the session

This means Stage 2 works from the same human-facing artifact Stage 1 already produced, rather than forcing an intermediate battery-shaped document too early.

## Proposed Stage 2 Flow

Recommended runtime flow:

1. Stage 1 reaches `stage1_ready`.
2. Stage 2 builds a proof-draft request from the Stage 1 brief and transcript.
3. AI returns a structured proof draft.
4. Code validates:
   - source grounding
   - allowed operation vocabulary
   - arithmetic correctness
   - comparison correctness
   - reference integrity
   - ambiguity policy
5. Code accepts, downgrades, or rejects the AI draft.
6. Code emits the final Stage 2 verdict and diagnostics.

## Why This Direction

This approach is designed to preserve the right code/AI boundary.

AI is good at:

- identifying what claim the user is really making
- identifying which grounded facts matter
- suggesting a plausible proof path
- describing how one value should be derived from others
- attempting a refutation

Code is good at:

- rejecting ungrounded premises
- rejecting unsupported proof steps
- recomputing arithmetic deterministically
- re-running comparisons deterministically
- downgrading unsupported reasoning to `UNDECIDABLE`

## Non-Goals

This design does not aim to:

- support every business-decision shape in v1
- invent a universal business logic language
- guarantee that every successful Stage 1 case yields a supported or refuted Stage 2 verdict
- let AI introduce new premises, rules, or proof operators without code support

## Proof Draft Contract

The AI should return a proof draft object rather than a battery document.

Suggested shape:

```json
{
  "claim": "Opening the second downtown location achieves the stated 40% overall brand revenue increase target.",
  "premises": [
    {
      "id": "P1",
      "statement": "Projected monthly revenue for the new location is $40,000.",
      "kind": "fact",
      "source_locator": "working_context.what_we_know[5]"
    }
  ],
  "computations": [
    {
      "id": "C1",
      "op": "mul",
      "args": [
        { "ref": "P2" },
        { "literal": 0.05 }
      ],
      "result": 3750
    }
  ],
  "comparisons": [
    {
      "id": "K1",
      "lhs": { "ref": "C3" },
      "operator": ">=",
      "rhs": { "literal": 0.40 }
    }
  ],
  "verdict": "SUPPORTED",
  "refutation_attempt": "The proposal would fail if cannibalization were materially above 5% or if the target is not a hard gate."
}
```

## Premises

Each premise should be one grounded input the proof uses.

Recommended fields:

- `id`
- `statement`
- `kind`
- `source_locator`

Recommended `kind` values:

- `fact`
- `assumption`
- `target`

Rules:

- every premise must point to a grounded source in Stage 1 or the transcript
- no premise may introduce a new business fact that does not appear in the source material
- if the AI needs a premise that is not grounded, it should either:
  - omit it and note the gap
  - or mark the overall proof as incomplete

## Computations

Computations should be explicit deterministic derivation steps.

They should not be free-form prose.

They should use a small allowed operation vocabulary.

Recommended fields:

- `id`
- `op`
- `args`
- `result`

Recommended v1 operations:

- `add`
- `sub`
- `mul`
- `div`

Possible future additions:

- `min`
- `max`
- `abs`
- simple unit-normalization helpers if needed

Important rule:

Expand support by operation type, not by business scenario.

Bad expansion:

- add support for weekend shift decisions
- add support for second-location decisions

Good expansion:

- add ratio computation
- add percent-change computation
- add monthly-to-annual normalization

## Comparisons

Comparisons are the executable proof checks that turn derived values into support or refutation.

Recommended fields:

- `id`
- `lhs`
- `operator`
- `rhs`

Recommended v1 operators:

- `<`
- `<=`
- `>`
- `>=`
- `==`

This is deliberately small.

It covers many useful checks while keeping code validation simple and auditable.

## Why Not Free-Form Expressions

We should avoid allowing the AI to emit arbitrary expression strings such as:

```text
(projected_revenue - cannibalized_revenue) / current_revenue
```

That would require a parser and would increase the chance of ambiguous or unsupported syntax.

Instead, computations should use a small AST-like structure with explicit operations and references.

That lets code:

- validate every operation
- resolve every reference
- recompute every result
- reject unknown forms cleanly

## Validation Rules

Code should validate the proof draft with hard rules.

Minimum checks:

1. Every referenced premise or computation id exists.
2. Every premise source locator resolves to actual Stage 1 material.
3. Every operation belongs to the allowed operation vocabulary.
4. Every computation result recomputes exactly or within a defined numeric tolerance.
5. Every comparison re-runs deterministically against the recomputed values.
6. Unsupported or ambiguous proof steps do not count.
7. If the accepted proof is incomplete in a load-bearing way, the final verdict becomes `UNDECIDABLE`.

## Ambiguity Policy

A major risk in Stage 2 is false precision.

Examples:

- a success criterion may be an aspiration, not a hard approval gate
- a projected number may be a rough estimate, not a firm premise
- a metric may be underspecified by scope or time window

So code should not simply accept every AI-emitted comparison as a real decision gate.

Instead:

- AI may nominate a threshold as a proof-bearing comparison
- code may downgrade that comparison if the source statement is too ambiguous
- unresolved ambiguity should push the verdict toward `UNDECIDABLE`, not fake certainty

## Unsupported Reasoning Policy

We should not try to support every proof shape in v1.

If AI needs a proof step that cannot be expressed using:

- grounded premises
- allowed computations
- allowed comparisons

then code should reject that step and treat the proof as partially unsupported.

If the unsupported step is load-bearing, the final verdict should be `UNDECIDABLE`.

This is an honest limitation, not a failure.

## Example From Recent Logs

Using the recent `WP1` log flow:

- proposal: open a second downtown location
- target: increase overall brand revenue by 40%
- grounded values later surfaced:
  - initial capital expenditure = 200000
  - monthly operating cost = 15000
  - projected monthly revenue = 40000
  - current monthly revenue = 75000
  - customer shift percentage = 5%

A plausible AI proof draft could propose:

1. compute cannibalized revenue from current revenue and shift percentage
2. compute net new monthly revenue from projected new revenue minus cannibalized revenue
3. compute percent uplift relative to current revenue
4. compare that uplift against the 40% target

Code would then:

- verify each premise is grounded in Stage 1 output or answers
- recompute each arithmetic step
- rerun the final comparison
- decide whether the 40% statement is a hard enough gate to count

Possible result:

- keep the arithmetic
- keep the comparison structure
- still downgrade the final verdict to `UNDECIDABLE` if the target itself is too ambiguous or if load-bearing context remains unresolved

That is exactly the point of checked AI: the model may propose a reasonable proof path, but code determines whether that path actually survives validation.

## Relation To Existing Code

The current formalization path in [src/decision_prover/ai/formalization.py](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/src/decision_prover/ai/formalization.py) asks the AI to produce a normalized feasibility bundle and then compiles it into a battery-shaped wrapper.

The recommended direction is to replace or supplement that path with:

- `build_stage2_proof_request(...)`
- `generate_ai_proof_draft(...)`
- `validate_proof_draft(...)`
- `finalize_checked_verdict(...)`

Instead of trusting AI-produced semi-formal strings, the runtime should accept only the small structured proof vocabulary code knows how to execute.

## Suggested Implementation Order

1. Define the proof-draft Pydantic contract.
2. Implement source locator validation against Stage 1 output and transcript.
3. Implement the small computation evaluator for the initial operation set.
4. Implement comparison evaluation.
5. Implement verdict downgrade rules for unsupported or ambiguous proofs.
6. Update the Stage 2 AI prompt to return proof drafts instead of the current normalized bundle.
7. Add logging for unsupported operations and rejected proof steps.

## Key Risk

The main risk is not lack of structure.

The main risk is pretending the proof language is more general than it really is.

So the system should be explicit:

- the proof language is intentionally narrow
- unsupported reasoning is expected
- `UNDECIDABLE` is a valid and honest result
- the language should grow only when repeated real cases justify a new operation

## Bottom Line

The recommended Stage 2 architecture is:

- AI proposes a proof
- code checks the proof
- unsupported reasoning does not silently pass

That gives better coverage than a pure manual verifier and better auditability than a pure AI verdict.
