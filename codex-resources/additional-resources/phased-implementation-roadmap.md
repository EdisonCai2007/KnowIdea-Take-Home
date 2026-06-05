# Phased Implementation Roadmap

Status: Finalized implementation breakdown  
Date: June 5, 2026

This document is a companion to [finalized-roadmap.md](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/codex-resources/additional-resources/finalized-roadmap.md). It does not replace that roadmap. Its job is to turn the approved architecture and build order into implementation phases with runnable checkpoints after every stage.

## Working Rules For Every Phase

- Every phase must end in a runnable state.
- Every phase must add a real testable capability, not just internal scaffolding.
- The decision battery should be used throughout development, not only at the end.
- Before full verifier coverage exists, all 12 battery cases must still import and parse cleanly.
- Hard constraints must remain the first-class decision path throughout the build.
- Stage 1 must never invent missing premises just to keep a flow moving.

## Phase 1: Shared Contracts And Fixture Import

### Goal

Create the project skeleton and lock the structured contracts that every later phase depends on.

### Build Scope

- Set up the Python project structure and stable entrypoints for fixture validation, verifier runs, proposal runs, and UI launch.
- Define the shared models for:
  - normalized decision input
  - company facts
  - hard constraints
  - action payloads
  - stated assumptions
  - derivation steps
  - binding constraint results
  - refutation results
  - undecidable details
  - final verification result
- Implement import and validation for `decision_battery.json`.
- Implement structured output serialization so verifier results have one stable shape from the start.

### Runnable Checkpoint

A CLI command can load the full battery, validate every company and decision object, and emit normalized structured records without running any business-logic verification yet.

### Battery/Test Gate

- All 12 battery decisions load successfully.
- Schema validation tests cover required fields, units, assumptions, and output serialization.
- Failure cases for malformed fixtures are rejected with readable errors.

### Exit Criteria

- The codebase has one canonical input contract and one canonical output contract.
- The repo is runnable by another engineer without guessing data shapes.
- Later rule work can build on typed structures instead of raw dictionaries.

## Phase 2: Deterministic Verifier Spine

### Goal

Build the core Stage 2 execution path before adding full rule coverage.

### Build Scope

- Implement verifier orchestration with a fixed precedence order:
  1. hard constraints
  2. explicit dominance checks
  3. objective satisfaction
- Add an append-only derivation builder that records checked steps as verification runs.
- Add classification handling for `SUPPORTED`, `REFUTED`, and `UNDECIDABLE`.
- Add explicit unsupported-rule coverage tracking so unimplemented logic cannot silently produce a fake verdict.

### Runnable Checkpoint

A verifier command can accept any normalized battery item, route it through the deterministic Stage 2 spine, and return a contract-compliant result even if some cases are still marked as not-yet-covered internally.

### Battery/Test Gate

- Covered-subset battery tests pass for reserve floor, runway, and initiative-budget behavior.
- All 12 battery decisions still pass import smoke and route through the verifier without crashing.
- Tests confirm hard-constraint precedence over upside claims.

### Exit Criteria

- Stage 2 has a real deterministic backbone.
- Derivations are produced during checking, not reconstructed after the fact.
- The system can honestly distinguish between a verified result and incomplete rule coverage.

## Phase 3: Full Rule Coverage For The Battery

### Goal

Implement the primary inference families and reach full verifier coverage on the decision battery.

### Build Scope

- Add rule evaluators for:
  - cash reserve floor checks
  - maintained runway checks
  - initiative budget caps
  - LTV/CAC checks
  - margin hurdle checks
  - marketing spend cap checks
  - capacity and backlog feasibility
  - explicit baseline or dominance comparisons
  - flip-threshold solving for undecidable cases
- Ensure every decisive rule contributes structured derivation steps and binding-constraint explanations.
- Ensure `UNDECIDABLE` returns include pivotal assumption and flip threshold when computable.

### Runnable Checkpoint

The verifier can run against the full battery and produce audit-ready Stage 2 outputs with checked verdicts, derivations, binding constraints, load-bearing assumptions, and refutation attempts.

### Battery/Test Gate

- Full `decision_battery.json` regression passes expected classifications.
- Constraint-refuted cases identify the actual violated constraint.
- `UNDECIDABLE` cases identify the pivotal assumption and threshold payload.
- Rule-specific unit tests cover arithmetic, feasibility, and precedence behavior.

### Exit Criteria

- Stage 2 is strong enough to stand on its own as the scored core deliverable.
- The battery can now be used as a hard regression suite.
- The verifier contract is stable enough for Stage 1 and UI work to build against.

## Phase 4: Premise-Locked Stage 2 AI Assist

### Goal

Add limited AI assistance to Stage 2 without giving it authority over truth, premises, or verdicts.

### Build Scope

- Add an AI-assisted layer for candidate proof drafting, refutation phrasing, and readable summaries.
- Enforce premise locking so the AI cannot introduce new facts, constraints, or proof steps.
- Reject any AI-proposed step that cannot be grounded in the normalized input and validated by code.
- Keep the deterministic verifier as the final authority on classification and checked derivation.

### Runnable Checkpoint

The verifier can run with AI assistance enabled or disabled, and both modes still return the same verified classification and checked reasoning structure.

### Battery/Test Gate

- AI-on and AI-off runs match on classification across the full battery.
- Validation tests prove unsupported AI steps are dropped rather than accepted.
- Regression tests confirm the output contract remains unchanged.

### Exit Criteria

- Stage 2 gains readability help without losing audit integrity.
- The README can clearly defend the code-versus-model boundary.
- No black-box reasoning path is allowed into the final verdict.

## Phase 5: Stage 1 Planner And Formalizer

### Goal

Build the interview and formalization flow around what the verifier actually needs to know.

### Build Scope

- Implement a verifier-driven gap agenda for missing action details, facts, constraints, objectives, and assumptions.
- Implement targeted clarification questions where each question names the verification check it unlocks.
- Build transcript capture for proposal, questions, answers, and formalization outcome.
- Normalize the interview result into the same shared decision schema used by Stage 2.

### Runnable Checkpoint

Each proposal from `nl_proposals.md` can run through Stage 1 and produce either:

- a `ClarificationNeeded` result with concrete questions and a gap list
- a Stage 2-ready normalized formal object

### Battery/Test Gate

- Stage 1 tests verify that under-specified proposals trigger clarification rather than fabricated values.
- Proposal-specific tests cover likely gaps in P1, P2, P3, P5, and P6.
- Noise-handling tests confirm irrelevant details such as the P4 logo remark are ignored.

### Exit Criteria

- Stage 1 is driven by proof needs rather than broad brainstorming.
- The formalizer can hand off a clean normalized object to Stage 2.
- The system can show its interview logic as an auditable artifact.

## Phase 6: Grounding Checks And End-To-End Pipeline

### Goal

Make the full two-stage system honest under missing information, approximate inputs, and assumption-sensitive outcomes.

### Build Scope

- Add blocking grounding checks for:
  - numeric facts used in verification
  - boolean or categorical facts used in verification
  - action parameters used in verification
  - hard constraints included in the formal object
- Implement approximate-value handling:
  - ask for exact values first
  - fall back to bounded ranges when exact values are unavailable
  - preserve unresolved uncertainty for Stage 2 threshold analysis
- Connect Stage 1 outputs directly into Stage 2 verification.

### Runnable Checkpoint

The end-to-end pipeline can take a raw proposal, run the interview, produce a normalized object, and return a checked verdict or an honest undecidable/needs-clarification outcome.

### Battery/Test Gate

- End-to-end runs over `nl_proposals.md` are saved as transcripts plus formal objects plus verdicts.
- Grounding tests fail if any verifier-used premise lacks a source in the proposal, answers, or provided structured input.
- Range-sensitive tests confirm that verdict flips become explicit `UNDECIDABLE` behavior rather than hidden assumptions.

### Exit Criteria

- The two-stage product behavior now matches the assignment's core honesty requirement.
- Missing proof-critical information is surfaced, not patched over.
- The pipeline is ready for UI integration using real outputs.

## Phase 7: Audit UI And Submission Assembly

### Goal

Build the plain audit-first interface and package the final submission artifacts on top of real system behavior.

### Build Scope

- Build a simple Streamlit UI using saved and live pipeline outputs.
- Required views:
  - interview transcript
  - missing-information trace or gap list
  - formal object
  - derivation steps
  - binding constraints
  - load-bearing assumptions
  - refutation output
- Add run instructions, README content, and walkthrough support around the finished system.

### Runnable Checkpoint

A reviewer can launch the UI, inspect one raw proposal end to end, inspect one battery item directly through Stage 2, and trace the final verdict to its formal object and checked derivation.

### Battery/Test Gate

- UI smoke tests confirm every required view renders from live or recorded real outputs.
- Manual demo flow covers at least one `UNDECIDABLE` result and one hard-constraint refutation.
- Submission checks confirm the repo includes runnable commands, battery output, proposal output, README, and walkthrough material.

### Exit Criteria

- The system is inspectable by a skeptical human without reading the source first.
- The deliverable package is complete and aligned with the assignment scoring priorities.
- The final demo uses real verified outputs rather than mocked examples.

## Recommended Execution Order

1. Finish Phases 1 through 3 before touching Stage 1.
2. Add Phase 4 only after deterministic Stage 2 behavior is stable.
3. Build Stage 1 in Phases 5 and 6 against the already-proven verifier boundary.
4. Leave the UI for Phase 7 so it reflects real artifacts instead of mocked placeholders.

## Definition Of Success

- After every phase, the code runs and something meaningful can be tested immediately.
- The battery becomes stronger as the build advances, never weaker.
- Stage 1 stays conservative about missing premises.
- Stage 2 stays deterministic about verdicts.
- The final system is auditable at both the formalization layer and the verification layer.
