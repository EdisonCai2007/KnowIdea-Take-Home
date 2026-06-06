# Stage 1 Interviewer + Context Updater Workflow

Date: June 6, 2026
Status: Locked Stage 1 Contract

## Purpose

This document defines the current Stage 1 contract in plain English.

Stage 1 is a clarification workflow, not a verifier workflow.
It should understand the proposal well enough to ask useful proof-critical questions, build a stable decision brief, and stop cleanly without drifting into Stage 2.

## Stage 1 Goal

Stage 1 is not trying to:

- fill out Decision Battery
- classify action types
- force the proposal into a rigid verifier schema
- make a final verifier judgment

Stage 1 is trying to:

- understand what the user is deciding
- understand the user’s objective
- surface only the missing proof-critical inputs
- maintain a lightweight decision brief
- stop once no more good clarification questions remain or the round cap is reached

## AI Roles

Stage 1 uses 3 AI steps and no separate readiness AI.

### 1. Initial Context AI

Its job is to:

- read the proposal and company context
- restate the decision clearly
- restate the objective clearly
- build the initial decision brief

### 2. Clarification Question AI

Its job is to:

- inspect the current brief
- ask 1 to 3 strong proof-critical questions
- return an empty list when no worthwhile question remains
- provide exactly 3 exact-value suggested answers for each asked question

### 3. Context Updater AI

Its job is to:

- take the current decision brief
- take the user’s raw answers
- update what we know
- update what still matters
- keep the brief stable and compact

## What Stage 1 Tracks

Stage 1 keeps a lightweight decision brief, not a verifier schema.

The brief contains:

- `decision`
- `objective`
- `what_we_know`
- `what_still_matters`
- `constraints_mentioned`
- `success_criteria`
- `notes`

This structure organizes understanding.
It does not pretend to be formal verification input.

## Workflow

1. The user provides company context and a proposal.
2. Initial Context AI builds the first decision brief.
3. Clarification Question AI decides whether there are 1 to 3 strong proof-critical questions to ask.
4. If the question list is empty, Stage 1 stops and returns `stage1_ready`.
5. If questions are returned, the user can:
   - click any suggestion
   - edit a suggestion
   - type a custom answer
6. Context Updater AI updates the brief using the user’s raw answers.
7. Clarification Question AI runs again on the updated brief.
8. Stage 1 repeats until either:
   - no more good questions remain
   - or the round cap is reached

## Question Quality Rules

A clarification question is good only if it helps decide the proposal.

A good question usually clarifies:

- cost
- timing
- constraints
- expected impact
- success criteria
- other exact proof-bearing thresholds

A bad question is:

- filling in a schema blank
- asking for taxonomy
- asking for action type
- asking for broad background that would not change the decision
- asking for planning detail that is not load-bearing right now

Simple test:

If the answer would not materially change a later feasibility, threshold, constraint, or objective-impact check, do not ask it.

## Suggested Answers Rule

Every asked clarification question must include exactly 3 suggested answers.

Those suggested answers must be:

- specific to the question
- directly responsive
- exact-value only

Good:

- `$50,000`
- `September 1, 2026`
- `14 months of runway`

Bad:

- `about $50,000`
- `less than $60,000`
- `roughly five months`
- `best estimate`
- `unknown for now`

Additional rules:

- Suggested answers must be exact literal values with units, dates, counts, percentages, rates, capacities, thresholds, or another similarly exact measurable input.
- Do not use ranges.
- Do not use approximation language such as `about`, `around`, or `roughly`.
- Do not use inequality phrasing such as `less than`, `more than`, `at least`, or `up to`.
- Do not use categorical suggested answers.
- If a potentially useful question cannot be expressed with exact-value suggested answers, skip that question instead of emitting low-quality suggestions.

## User Answer Behavior

The user should be able to:

- choose any of the 3 suggested answers
- type a completely custom answer
- edit a chosen suggestion before submitting

The UX should behave like Codex planning questions:

- clicking a suggestion should prefill the answer box with that exact suggestion
- the user should still be able to edit the text before submitting

## Rounds Rule

Default behavior:

- 1 to 3 questions per round
- max 3 rounds total

After round 3, Stage 1 should stop and mark the proposal ready with unresolved notes rather than keep looping.

## Stop Rule

Stage 1 does not use a separate readiness AI.

It stops when either:

- the Clarification Question AI returns no more good questions
- or the max-round limit is reached

The ready output should still include:

- the final decision brief
- the transcript
- a short summary of why Stage 1 stopped
- unresolved notes if any remain

## Revision Rule

The AI may refine its understanding, but it should not replace the core decision unless the user clearly corrected it.

Allowed:

- making the decision more precise

Not allowed:

- changing the meaning of the proposal without an explicit user correction

## If Questions Are Weak

Do not regenerate questions inside the same round.

If questions are weak, that is a prompt-quality problem.
The user should still be able to answer, skip, or continue the workflow.

## Stage 1 to Stage 2 Boundary

Stage 1 ends with a decision brief and transcript.

A later translation step may convert that into Stage 2 structure, but that translation is outside this workflow.

Do not mix formalization or verification structure into the clarification loop.

## Big Principles

- Keep Stage 1 human-facing.
- Keep it AI-driven but bounded.
- Keep it separate from verifier structure.
- Ask only what materially helps decide the proposal.
- Prefer exact proof-bearing inputs over soft planning detail.
- Stop cleanly when no more strong questions remain.
