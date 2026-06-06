# Stage 1 -> Stage 2 AI Formalization Draft

Date: June 6, 2026
Status: Draft

## Summary

Add a new **post-Stage-1 AI formalization step** that runs **after** the current `stage1_ready` outcome and produces a **single-company, single-decision `DecisionBattery` JSON document** for Stage 2.

This step is a handoff layer, not a rewrite of Stage 1.

Stage 1 stays as the current lightweight brief + transcript workflow.
The new AI formalizer consumes:

- active workspace company context
- original proposal text
- Stage 1 working context
- Stage 1 transcript
- clarification answers already captured in the session

The formalizer outputs:

- one valid `DecisionBattery` document
- exactly one company entry
- exactly one decision entry
- no classification inside that document

The existing deterministic verifier then consumes that formalized output and produces `SUPPORTED`, `REFUTED`, or `UNDECIDABLE` as a **separate Stage 2 result**.

## Key Decisions

- Use a **full battery-shaped wrapper** first, not just a raw `DecisionContext`.
- Keep Stage 1 and Stage 2 **separate**.
- Run formalization as a **post-ready handoff step**, not inside the current Stage 1 questioning loop.
- Do **not** embed classification in the handoff JSON.
- Reuse the existing battery metadata instead of inventing new constants:
  - `battery_version`
  - `title`
  - `note_to_candidate`
  - `verdict_definitions`
  - `schema`
- For v1, copy those top-level metadata fields **verbatim from the canonical battery fixture**.
- Prefer **grounded omission over invention**:
  - if a fact, constraint, action parameter, or assumption is not grounded in proposal/workspace/answers/transcript, do not invent it
  - emit empty `facts`, empty `constraints`, or an incomplete-but-valid action only when the schema allows it
- If the action does not fit an existing typed action family cleanly, use the existing **generic action payload** shape rather than forcing a wrong typed action.

## Implementation Changes

### 1. New handoff contract

Add a new post-Stage-1 formalization result shape for workspace proposals.

Recommended fields:

- `status`: `formalized` or `formalization_error`
- `battery_document`: full one-company one-decision `DecisionBattery`
- `primary_decision_id`: workspace proposal id
- `grounding_report`: source traceability for every emitted verifier-used field
- `notes`: non-blocking formalization notes

Do **not** change the current `Stage1WorkingContext` contract into verifier schema.

### 2. Formalization rules

The AI formalizer must create a valid `DecisionBattery` document with:

- `companies[0].id`
  - canonicalized from workspace company name
- `companies[0].name`
  - workspace company name
- `companies[0].sector`
  - workspace company sector
- `companies[0].facts`
  - only grounded facts from proposal text, clarification answers, and transcript
- `companies[0].constraints`
  - only grounded hard constraints explicitly stated by the user or clearly captured during Stage 1
- `decisions[0].id`
  - workspace proposal id
- `decisions[0].company`
  - same as `companies[0].id`
- `decisions[0].proposal`
  - original proposal text
- `decisions[0].action`
  - AI-inferred structured action from grounded proposal/answers
- `decisions[0].objective`
  - Stage 1 objective, refined only when grounded by user input
- `decisions[0].stated_assumptions`
  - only assumptions explicitly stated by the user or clearly unavoidable and labeled as assumptions by the formalizer

### 3. Grounding policy

Every emitted verifier-used field must have a source entry.

Minimum source categories:

- `workspace`
- `proposal`
- `answer`
- `stage1_summary`

Each grounding entry should include:

- emitted field path
- source type
- source quote
- source locator

If a field cannot be grounded, omit it instead of fabricating it.

### 4. Validation and verifier boundary

After AI output:

- validate the full JSON with the existing `DecisionBattery` Pydantic contract
- normalize it through the existing battery loader / decision-context path
- run the current verifier and optional explain layer unchanged

If formalization output is invalid JSON or schema-invalid:

- return `formalization_error`
- preserve the Stage 1 ready state and transcript
- do not guess missing fields in code except for copied top-level battery metadata

### 5. Scope limit for v1

This first version should be intentionally narrow:

- one active company
- one proposal
- one generated battery document
- no multi-decision packing
- no assumption toggling
- no attempt to infer broad company profiles from description-only text
- no forced extraction of constraints when the user never stated them

## Test Plan

Cover these scenarios:

- A proposal with enough specifics formalizes into a valid one-company one-decision `DecisionBattery`.
- A proposal that needed clarification uses transcript answers in the final action/objective/facts.
- Top-level metadata matches the canonical battery fixture exactly.
- Workspace name/sector appear in the formalized company object.
- Unsupported action families fall back to generic action payload instead of invalid typed action coercion.
- Ungrounded facts and constraints are omitted rather than invented.
- Formalized output contains no classification field.
- The formalized battery document can be normalized into the existing Stage 2 verifier input.
- Invalid AI JSON yields `formalization_error` without corrupting the Stage 1 ready session.
- A sparse but valid formalization can still proceed to Stage 2 and honestly end in `UNDECIDABLE` or coverage-gap behavior.

## Assumptions And Defaults

- The canonical source for copied battery metadata is the existing `decision_battery.json` fixture.
- Stage 1 remains the current lightweight decision-brief system and is not expanded into full verifier formalization.
- Formalization is an AI-led step, but code remains responsible for schema validation and verifier execution.
- `classification` belongs only to Stage 2 output, not the handoff artifact.
- The first draft should optimize for **valid, grounded, minimal JSON**, not maximal inference coverage.
