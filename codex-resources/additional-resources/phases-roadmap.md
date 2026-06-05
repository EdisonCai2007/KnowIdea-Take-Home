# Phases Roadmap

Status: Follow-on roadmap from current Phase 4 state  
Date: June 5, 2026

This document continues from the repo's current Phase 4 implementation state described in [README.md](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/README.md) and narrows the remaining work around the approved single-company product workflow in [finalized-roadmap.md](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/codex-resources/additional-resources/finalized-roadmap.md).

Phases 1 through 4 remain as already planned and implemented. This roadmap covers the next phases only.

## Working Assumption

V1 is one company at a time:

- one active company workspace
- one company intake flow before proposal entry
- one proposal-driven clarification loop inside that company context
- no multi-company switcher in the main workflow

If we later add support for multiple companies, it should be through separate company workspaces or chats rather than one mixed context.

## Phase 5: Single-Company Workspace And Intake

### Goal

Establish the v1 product shell around one active company context before building the full Stage 1 interview experience.

### Build Scope

- Add a landing flow that captures lightweight company context:
  - company name
  - sector
  - optional short description
- Represent one active company workspace in the UI and app state.
- Distinguish lightweight company identity from proof-bearing facts used by the verifier.
- Block proposal analysis until the active company workspace has been created.

### Runnable Checkpoint

A reviewer can launch the app, create one company workspace, and reach a proposal-entry surface that is clearly scoped to that company.

### Acceptance Gate

- The UI supports one active company only.
- Company setup is visible and editable before proposal submission.
- No multi-company navigation, switching, or chat management is introduced in v1.

### Exit Criteria

- The product shape matches the agreed single-company workflow.
- Company intake exists without pretending that company identity alone is a formal decision object.

## Phase 6: Proposal Intake And Stage 1 Clarification

### Goal

Attach the proposal flow to the active company workspace and make Stage 1 visibly interview-driven.

### Build Scope

- Add a proposal input surface inside the active company workspace.
- Start Stage 1 only after a proposal is submitted.
- Generate targeted clarification questions tied to missing verification needs.
- Capture the proposal, clarification prompts, user answers, and gap agenda as an auditable transcript.
- Ignore non-load-bearing noise unless it affects a supported rule family.

### Runnable Checkpoint

Within one company workspace, a reviewer can enter a proposal and receive either:

- targeted clarification questions
- or a Stage 2-ready formalization when the proposal already contains enough information

### Acceptance Gate

- Under-specified proposals trigger real clarification instead of invented values.
- The transcript makes it clear why each question was asked.
- The active company context stays stable while the proposal is being clarified.

### Exit Criteria

- The user flow now reaches a genuine Stage 1 interview.
- Proposal intake is clearly separate from initial company setup.

## Phase 7: Grounded Formalization And Verified Handoff

### Goal

Turn the company workspace plus proposal transcript into a grounded formal object and pass it into Stage 2 without losing source traceability.

### Build Scope

- Merge company facts, hard constraints, proposal details, and stated assumptions into one normalized single-company decision context.
- Preserve grounded sources for every verifier-used field.
- Run the deterministic verifier and the existing Phase 4 AI second-opinion layer against that normalized context.
- Surface `ClarificationNeeded`, `SUPPORTED`, `REFUTED`, and `UNDECIDABLE` outcomes cleanly in the workflow.

### Runnable Checkpoint

A reviewer can go from company intake to proposal to clarification to a verified outcome without leaving the same company workspace.

### Acceptance Gate

- Every verifier-used fact is traceable to the proposal, user answers, or structured input.
- `UNDECIDABLE` outcomes name their pivotal assumption in the company workflow, not only in backend outputs.
- The AI advisory layer remains side-by-side with the deterministic verdict and never overrides it.

### Exit Criteria

- The one-company workflow is now end to end.
- The system remains honest about missing information and assumption-sensitive outcomes.

## Phase 8: Audit-First Review Surface And Submission Readiness

### Goal

Finish the v1 experience as a reviewable single-company audit tool and package the required submission artifacts around real outputs.

### Build Scope

- Present the active company summary, proposal, interview transcript, formal object, derivation, binding constraints, assumptions, and refutation in one audit-first flow.
- Make the verdict traceable to the exact failing constraint or pivotal assumption.
- Support one clean walkthrough that starts from company intake and ends at an auditable result.
- Assemble README, recorded outputs, and walkthrough material using the real single-company flow.

### Runnable Checkpoint

A reviewer can run the app, create a company workspace, submit a proposal, inspect the full audit trail, and understand why the final verdict was reached.

### Acceptance Gate

- The UI demonstrates one full company-specific journey from intake to verdict.
- At least one hard-constraint refutation and one `UNDECIDABLE` case are reviewable through the same audit surface.
- Submission materials describe the single-company workflow explicitly.

### Exit Criteria

- The product is coherent as a v1 single-company Decision Prover.
- The submission tells the same story as the implementation.

## Deferred After V1

- multiple company workspaces in one session
- chat or workspace switching across companies
- assumption editing and live verdict toggling
- broader CRM-style company profile management

These are valid extensions, but they should not dilute the one-company-at-a-time workflow in v1.
