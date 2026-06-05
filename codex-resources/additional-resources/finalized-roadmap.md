# Finalized Roadmap

Status: Final
Date: June 5, 2026

This roadmap supersedes [architecture-roadmap.md](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/architecture-roadmap.md) where the two documents differ.

## Goal

Build a two-stage Decision Prover that:

- interviews and formalizes vague business proposals without inventing premises
- verifies the resulting structured object against explicit facts, constraints, and assumptions
- returns `SUPPORTED`, `REFUTED`, or `UNDECIDABLE`
- shows an auditable derivation a skeptic can inspect

## Non-Negotiable Rules

1. The public product stays a two-stage system:
   - `Stage 1`: interview and formalize
   - `Stage 2`: verify and refute
2. Stage 1 must elicit missing load-bearing information instead of fabricating it.
3. Stage 2 may use AI, but it may not introduce any new premises, constraints, or proof steps that are not grounded in the Stage 1 output or the already-formalized input.
4. The final verdict must be one of:
   - `SUPPORTED`
   - `REFUTED`
   - `UNDECIDABLE`
5. Hard-constraint violations take precedence over upside or projected returns.
6. Every Stage 2 result must include:
   - derivation
   - binding constraints
   - load-bearing assumptions
   - refutation attempt
7. Stage 1 output must normalize to the schema shape used by [decision_battery.json](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/decision_battery.json).

## Final Architecture

### Stage 1: Interview and Formalize

Stage 1 is LLM-led. Its job is to turn a natural-language proposal into a structured decision object without hallucinating facts.

Internal responsibilities:

- detect the proposed action, objective, known facts, hard constraints, and stated assumptions
- identify what is missing for a valid proof or refutation
- ask targeted clarification questions tied to a specific verification need
- produce a normalized structured object for Stage 2

Stage 1 should be internally organized as:

- `planner`
- `formalizer`
- `grounding check`

The planner should stay flexible on variable names, but narrow on reasoning scope. We should not hardcode exact field names like `cost` or `spend` as the only acceptable concepts. We should instead scope around the inference families we actually plan to support.

### Stage 2: Verify and Refute

Stage 2 is hybrid:

- AI helps draft candidate reasoning, proof structure, refutation paths, and readable explanations.
- Code checks the math, constraints, assumptions, and rule validity.

The key rule is premise locking:

- the AI may reorganize or explain the premises
- the AI may not invent a missing premise
- the AI may not smuggle in a new constraint
- the AI may not turn an unsupported claim into a proof step

Code remains the final authority on:

- verdict classification
- arithmetic and unit checks
- hard-constraint evaluation
- dominance checks
- threshold / flip-point logic for `UNDECIDABLE`
- whether each derivation step is actually supported

If the AI proposes a proof step that cannot be grounded in the formal object or validated by the rule set, that step is rejected. If no valid proof or refutation remains after checking, the system returns `UNDECIDABLE`.

## Supported Reasoning Scope

We should scope tightly around the assignment's intended inference vocabulary, not around a giant business ontology.

Primary inference families for v1:

- cash balance and reserve-floor checks
- runway checks
- initiative budget caps
- LTV/CAC and unit economics
- margin hurdle checks
- marketing spend cap checks
- capacity and backlog feasibility
- explicit baseline or dominance comparisons

This keeps the system narrow enough to be reliable while still allowing flexible fact names and proposal wording.

## Stage 1 Questioning Policy

Every clarification question must unlock a concrete verification check.

Good reasons to ask:

- a load-bearing quantity is missing
- a hard constraint is implied but underspecified
- the action itself is too vague to formalize
- the objective is unclear
- the user gave an approximate value that could affect the verdict

Bad reasons to ask:

- curiosity
- broad brainstorming
- collecting non-load-bearing context
- forcing the proposal into an unnecessary taxonomy

Question style should be explicit about why the answer is needed, for example:

- "What is the fully loaded annual cost per hire? I need it to check runway and reserve constraints."
- "What is the delivery deadline? I need it to check whether current capacity can satisfy the backlog."

## Approximate Value Policy

If the user gives an approximate quantity like "about 80k" or "roughly five months," Stage 1 should ask to pin it down when that value is load-bearing.

Preferred handling order:

1. ask for an exact value
2. if exact is unavailable, ask for an explicit bounded range
3. if the user will not narrow it, store the uncertainty as an explicit assumption or range and let Stage 2 determine whether the verdict flips across that range

The default behavior is to clarify first, not to silently convert approximations into point estimates.

## Grounding and Critic Policy

We should simplify the earlier critic design for v1.

Required blocking checks in code:

- every numeric fact used in verification must have a grounded source
- every boolean or categorical fact used in verification must have a grounded source
- every action parameter used in verification must have a grounded source
- every hard constraint included in the formal object must be grounded in the proposal, user answers, or provided structured input

For v1, we should not put a separate model-driven "semantic drift critic" in the critical path. That adds complexity without enough score benefit.

Optional AI review can still be used for:

- readability checks
- spotting wording inconsistencies for developer review

But those findings should be advisory unless they map to a concrete grounding failure.

## Output Contract

### Stage 1 Output

Stage 1 must normalize into the same boundary shape used in the battery:

- company facts
- hard constraints
- decision action
- objective
- stated assumptions

Internally, we can use helper structures like a gap agenda. Externally, Stage 2 should receive one clean normalized object.

### Stage 2 Output

Stage 2 must always return:

- `classification`
- `derivation`
- `binding_constraints`
- `load_bearing_assumptions`
- `refutation`

For `UNDECIDABLE`, it must also return:

- `pivotal_assumption`
- `flip_threshold` when one can be computed
- the conditions under which the decision would be supported vs. refuted

## Evaluation Fixtures

We should keep the original spec artifacts in the test loop:

- [nl_proposals.md](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/codex-resources/original-project-specs/nl_proposals.md) is the Stage 1 evaluation set for interview quality, gap detection, and translation from raw user language into the normalized schema.
- [decision_battery.json](/Users/edisoncai/Documents/GitHub/KnowIdea-Take-Home/codex-resources/original-project-specs/decision_battery.json) is the Stage 2 evaluation set for derivation validity, verdict correctness, and output-contract compliance on already-structured inputs.
- End-to-end testing should cover both paths: formalize proposals from `nl_proposals.md`, then pass the resulting structured object into Stage 2.

## UI Scope

The UI should stay plain and audit-first.

Required views for v1:

- interview transcript
- missing-information trace or gap list
- formal object
- derivation steps
- binding constraints
- load-bearing assumptions
- refutation output

Stretch goal status:

- do not build assumption toggling in v1
- keep the verifier interface reusable so assumption editing can be added later
- mention the stretch goal as a future enhancement, not a current commitment

## Build Order

1. Define the shared types and the normalized formal-output contract.
2. Implement the Stage 2 checker and derivation validator against the battery schema.
3. Build the core rule set for the primary inference families.
4. Add refutation paths:
   - hard-constraint breakage
   - explicit dominance checks
   - threshold solving for undecidable cases
5. Add the Stage 2 AI layer for candidate proof drafting and readable explanation, with premise locking and step validation.
6. Build Stage 1 planner and formalizer around verifier needs.
7. Add grounding checks for Stage 1 outputs.
8. Build the audit UI on top of real outputs, not mocked ones.

## What We Are Explicitly Not Doing in v1

- building a general theorem prover
- supporting arbitrary business logic outside the scoped inference families
- letting an LLM own the final verdict
- letting an LLM invent premises to complete a proof
- treating the assumption-toggle UI as a required deliverable
- adding a heavy semantic-drift critic that acts like a second verifier

## Resolved Contradictions and Tensions

### Contradiction 1

Stage 2 should use AI, but only inside a checked pipeline. AI can help construct and explain a proof, but it cannot introduce new premises. Final conclusions must still be derived from Stage 1 premises and validated checks, resulting in `SUPPORTED`, `REFUTED`, or `UNDECIDABLE`.

### Contradiction 2

The assumption-toggle UI stays a stretch goal. We will keep it as a reminder for later, but it is not part of the current implementation target.

### Tension 1

We should leverage AI more in Stage 2 than the prior roadmap allowed, but only with code validation. This is now the official direction.

### Tension 2

We should scope the system more tightly, but not by freezing exact variable names like `cost` and `spend`. The scope should be the supported reasoning families and rule types, not a brittle list of allowed field names.

### Tension 3

Whenever a load-bearing quantity is approximate, we should ask the user to tighten it. If they cannot, we preserve that uncertainty explicitly instead of pretending it is exact.

### Tension 4

The earlier hybrid critic idea is removed from the critical path for v1. Grounding checks stay, but we are not building a complicated semantic-drift judge right now.

## Success Criteria

- Stage 1 asks for missing proof-critical information instead of inventing it.
- Stage 1 produces normalized structured objects that match the verifier boundary.
- Stage 2 never uses ungrounded premises.
- Stage 2 returns auditable derivations and real refutation attempts.
- Hard constraints are checked before upside or optimization claims.
- `UNDECIDABLE` is treated as a first-class honest outcome, not as a failure mode to hide.
