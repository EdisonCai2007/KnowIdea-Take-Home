# Stage 2 Light Formalization Specification

Date: June 6, 2026
Status: Draft

## Purpose

This document defines a lighter and more honest Stage 2 formalization approach.

The goal is not to make Stage 1 fill out verifier-shaped blanks.
The goal is to help the user clarify a decision, then convert only the grounded parts of that understanding into a verifier-ready structure.

This spec reflects two principles:

- prefer grounding over guesswork
- prefer omission over invention

## Core Position

Stage 1 and Stage 2 should not behave like the same system with different field names.

They have different jobs:

- Stage 1 is human-facing clarification
- Stage 2 formalization is evidence packaging for verification

That means Stage 1 should not be forced to act like a schema form.
It should focus on understanding the user, surfacing proof-critical missing information, and stopping cleanly when no more strong questions remain.

Stage 2 should then translate that material into a structured object that the verifier can inspect honestly.

## Recommended Architecture

Use a two-layer input model:

1. A lightweight Stage 1 decision brief
2. A stricter Stage 2 proof object

The formalizer is the bridge between them.

This bridge should be narrow, explicit, and conservative.

## Layer 1: Stage 1 Brief

Stage 1 should continue to track a lightweight brief such as:

- decision
- objective
- what we know
- what still matters
- constraints mentioned
- success criteria
- notes

This is a conversation artifact, not a proof artifact.

It should stay readable and flexible.
It should not be judged by whether it perfectly fills verifier fields.

## Layer 2: Stage 2 Proof Object

Stage 2 should still target the decision-battery-shaped structure because that is the verifier boundary and the assignment reference shape.

The formalized output should include:

- company facts
- hard constraints
- structured action
- objective
- stated assumptions

But this structure should be treated as a strict output contract, not as a template that must always be fully populated.

## Main Policy Change

The formalizer should stop trying to make every proposal look complete.

Instead:

- include fields when they are grounded
- omit fields when they are not grounded
- elevate unresolved but important unknowns into explicit assumptions when appropriate
- allow sparse but valid formalizations

The verifier should then be free to conclude `UNDECIDABLE` when the missing information is load-bearing.

## Grounding Rule

Every proof-bearing field used by verification should be traceable to a source.

Simple rule:

If a fact, action parameter, constraint, or assumption matters to the verdict, we should be able to point to where it came from.

Allowed source classes:

- workspace context
- original proposal text
- clarification answers
- Stage 1 summary or transcript-backed synthesis

Each grounded field should have a source record that names:

- emitted field path
- source type
- supporting quote or paraphrase
- source locator

## Omission-First Rule

When the user did not provide enough information, the system should not fake completeness.

Preferred behavior:

- fewer facts
- fewer constraints
- more explicit unresolved assumptions
- more honest `UNDECIDABLE` outcomes when needed

Disallowed behavior:

- inventing quantities because the schema looks empty
- inventing hard constraints because they are common in business
- pretending a projected outcome is a fact
- silently converting vague language into precise values without user grounding

## Optionality Rule

Stage 2 should remain strict about shape, but lighter about content density.

That means:

- the overall formalized document must still validate
- required wrapper fields must still exist
- individual action families may contain optional parameters when the user did not provide all details
- facts and constraints may be empty when nothing grounded is available
- the structured action may be partial if the action type is known but some parameters are missing

The key idea is:

valid but sparse is better than rich but fabricated

## Action Formalization Rule

Do not force every proposal into a narrow typed action family if doing so distorts the decision.

Preferred order:

1. use an existing typed action when the fit is natural
2. use a partial typed action when the action family is clear but some details are missing
3. use the generic action payload when a typed action would misrepresent the proposal

The objective is faithful representation, not taxonomy completion.

## Facts Rule

Facts should be included only when the user or supplied context actually gives them.

A fact should be:

- concrete
- attributable
- usable by verification

Good examples:

- cash balance
- monthly burn
- cost per hire
- delivery deadline
- budget cap stated by the user

Bad examples:

- inferred company maturity
- guessed conversion rate
- assumed staffing productivity
- unstated reserve floor

## Constraints Rule

Hard constraints are especially sensitive because a false constraint can wrongly refute a decision.

So constraints should only be included when they are grounded in one of these ways:

- explicitly stated in the proposal
- explicitly given by the user during clarification
- clearly established in structured input

Constraints should not be added just because they are common-sense policies.

If a possible constraint seems important but was never stated, Stage 1 should ask about it.
If Stage 1 is already over and it was never grounded, Stage 2 should omit it.

## Assumptions Rule

Assumptions are not failure.
They are honesty markers.

Use assumptions when:

- the user explicitly frames something as expected or projected
- the verdict depends on an uncertain input
- the system needs to preserve an unresolved but load-bearing condition

Do not disguise assumptions as facts.

Where possible, assumptions should be labeled in plain language so an auditor can see what the verdict rests on.

## Objective Rule

The objective should reflect what the user is actually trying to optimize or protect.

It should not be over-polished into a generic business goal.

If the user says:

- "hire faster without risking runway"

then the formalized objective should stay close to that meaning.

If the objective remains ambiguous after Stage 1, keep it simple and note the ambiguity rather than manufacturing a sharper goal than the user gave.

## Stage 1 Boundary

Stage 1 should not ask questions just to complete a schema.

It should only ask when the answer would materially help later verification.

Bad Stage 1 behavior:

- "What action type is this?"
- "What category should I store this under?"
- "Can you fill this missing field?"

Good Stage 1 behavior:

- "What is the budget? I need it to check feasibility."
- "What is the minimum cash floor? I need it to know whether this decision violates a hard constraint."
- "What exact hiring count are you considering? I need it to estimate cost and runway impact."

## Formalization Success Standard

A successful Stage 2 formalization is not the most complete object.

It is the most honest valid object.

Success means:

- the proposal is represented faithfully
- proof-bearing fields are grounded
- unverifiable gaps are not hidden
- the verifier receives enough structure to reason
- missing information remains visible instead of being quietly patched over

## Non-Goals

This spec does not require:

- redesigning the decision battery schema
- forcing all proposals into perfect action taxonomy coverage
- making Stage 1 act like a verifier form
- maximizing extraction density
- eliminating `UNDECIDABLE`

In fact, a healthy system should sometimes produce sparse formalizations that lead to `UNDECIDABLE`.

## Practical Recommendation

For the next implementation pass, treat the decision battery shape as the final transport format, but loosen the formalizer's behavior around it.

Specifically:

- preserve the strict wrapper
- keep validation
- keep the verifier boundary
- relax the urge to populate everything
- require grounding for verifier-used fields
- allow partial action objects
- allow empty facts or constraints where appropriate
- rely on assumptions and `UNDECIDABLE` rather than invented certainty

## Summary

The right direction is not to make Stage 2 less formal.
It is to make Stage 2 less dishonest.

That means:

- Stage 1 stays human
- Stage 2 stays structured
- the bridge becomes more conservative
- grounding becomes mandatory
- omission becomes acceptable
- uncertainty becomes explicit

This should produce a system that is closer to the assignment's real standard:
honest formalization feeding auditable verification.
