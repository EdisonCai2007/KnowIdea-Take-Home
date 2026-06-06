# Decision Prover

Decision Prover is a two-stage business-decision checker. It takes a proposed decision, asks for missing proof-critical information, turns the result into a semi-formal proof object, and returns a checked verdict: `SUPPORTED`, `REFUTED`, or `UNDECIDABLE`.

The goal is not to prove that a business decision is good in the abstract. The system proves only whether the decision follows from the stated facts, constraints, and assumptions. If the premises are incomplete, the honest result is `UNDECIDABLE`.

## What Is Included

- Stage 1 interview flow for natural-language proposals.
- Stage 2 verification for the provided `decision_battery.json`.
- Workspace proposal flow that turns a completed Stage 1 brief into a Stage 2 proof draft.
- Audit UI for inspecting the proposal, interview, formal object, derivation, binding constraints, assumptions, and refutation.
- Assignment output artifacts:
  - [Battery verifier output](codex-resources/assignment-output/battery-verifier-output.md)
  - [Proposal pipeline output](codex-resources/assignment-output/proposal-pipeline-output.md)

## Setup

Requires Python 3.11 or newer.

```bash
pip install -e .
```

Create a `.env` file or export the variables in your shell:

```bash
OPENROUTER_API_KEY=your_provided_openrouter_key
```

Useful optional environment variables:

```bash
OPENROUTER_STAGE1_MODEL=google/gemini-2.5-flash
OPENROUTER_STAGE2_MODEL=google/gemini-2.5-pro
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TIMEOUT_SECONDS=30
DECISION_PROVER_LOG_FILE=logs/decision_prover.log
```

`OPENROUTER_MODEL` is only a fallback when a stage-specific model is not set.

## Primary Workflow

Serve the audit UI:

```bash
decision-prover ui serve
```

Then open `http://127.0.0.1:8000`.

View the proposal pipeline output:

[Proposal pipeline output](codex-resources/assignment-output/proposal-pipeline-output.md)

```bash
decision-prover proposals run \
  --input codex-resources/original-project-specs/nl_proposals.md
```

View the decision battery output:

[Battery verifier output](codex-resources/assignment-output/battery-verifier-output.md)

```bash
decision-prover verify run \
  --input codex-resources/original-project-specs/decision_battery.json \
  --decision-id D3
```

## Architecture

The system has two related paths.

The first path is the direct battery verifier. `decision_battery.json` is already formalized, so the code loads each company and decision, normalizes it into a `DecisionContext`, and runs the deterministic verifier without asking the model to re-formalize it.

The second path is the natural-language proposal pipeline. Stage 1 uses OpenRouter to interview the user and produce a decision brief with transcript, known facts, unresolved notes, constraints mentioned, and success criteria. Once Stage 1 is ready, Stage 2 uses OpenRouter to draft an executable proof object. Code then validates the proof draft and converts it into the same user-facing verification result shape.

## Formalization Schema

The battery schema is the canonical Stage 2 input for already-formalized decisions.

At the company level, it contains:

- `id`, `name`, and `sector`
- typed `facts`, where each fact has a `value`, `unit`, and optional `note`
- `constraints`, limited to hard constraints with an id, natural-language statement, and semi-formal expression

At the decision level, it contains:

- `id`, linked `company`, and original `proposal`
- `action`, a structured JSON object with a required `type` and JSON-compatible parameters
- `objective`
- `stated_assumptions`, each tagged as `given` or `projected`

For workspace proposals, Stage 1 does not pretend to have a full battery object immediately. It first creates a decision brief:

- decision and objective
- what is known
- what still matters
- constraints mentioned
- success criteria
- transcript of proposal, questions, answers, and readiness decision

After Stage 1 is ready, the Stage 2 model drafts a proof object with:

- `claim`
- `premises`
- arithmetic `computations`
- executable `comparisons`
- `proposed_verdict`
- `refutation_attempt`
- `unresolved_gaps`

Code validates that proof draft before showing it as a checked result.

## Stage 1 Interview Rules

Stage 1 is designed to elicit rather than fabricate. It starts by extracting a lightweight working context from the proposal and company workspace. It then asks up to three clarification questions per turn, with suggested answers and a recommended answer. The questions target information that would materially affect proof feasibility, such as:

- missing quantities
- budget or runway floors
- target thresholds
- expected costs, revenue, margins, or capacity
- explicit success criteria

The interview stops when the model says no proof-critical questions remain, the user chooses to continue with unresolved notes, or the maximum clarification rounds are reached. Unanswered material is carried forward as unresolved context instead of being silently invented.

## Stage 2 Verifier And Inference Rules

For the battery fixture, the verifier is deterministic. The authoritative verdict comes from code, not from a model.

The verifier checks hard constraints before objectives. This matters because a decision that violates a hard constraint is `REFUTED` even if the projected upside is attractive.

Implemented inference families include:

- cash reserve floors
- runway floors
- initiative budget caps
- LTV/CAC thresholds
- production-capacity and backlog feasibility
- new SKU margin thresholds
- marketing spend caps
- price-change dominance checks
- objective checks for supported action families such as acquisition, hiring, channel tests, capex expansion, retention programs, supplier renegotiation, SKU launches, and line discontinuation

The output always uses the assignment result shape:

- `classification`
- ordered `derivation`
- `binding_constraints`
- `load_bearing_assumptions`
- `refutation`
- optional undecidable fields such as pivotal assumption and flip threshold

If required proof inputs are missing, the verifier returns `UNDECIDABLE` and names the missing inputs instead of manufacturing a proof.

## Code Vs Model Boundary

The model is used where natural language is unavoidable:

- Stage 1 interview planning and context extraction
- Workspace Stage 2 proof-draft generation from the completed Stage 1 brief
- Optional independent AI explanation for comparison with the deterministic battery verifier

Code owns the parts that must be checkable:

- schema validation with Pydantic
- fixture loading and decision-context normalization
- battery verdicts
- hard-constraint arithmetic
- dominance and objective checks
- proof-draft validation for workspace proposals
- final result formatting

Workspace Stage 2 proof drafts are model-generated, but the model is constrained to a small executable vocabulary: `add`, `sub`, `mul`, `div` computations and `<`, `<=`, `>`, `>=`, `==` comparisons. Code validates references, duplicate ids, division by zero, computation results, and comparison outcomes. If a decisive proof draft lacks executable comparisons, the validation report records that the checked classification is `UNDECIDABLE` and surfaces the issue for audit.

## Refutation Strategy

Refutation is part of the result, not an afterthought.

For hard constraints, refutation means searching for a direct violation first: reserve floor, runway floor, budget cap, unit-economics threshold, capacity deadline, margin threshold, or spend cap. If a violation is found, the decision is `REFUTED` immediately.

For objective and dominance checks, refutation means looking for missing proof material, failed comparisons, or a dominated alternative. When the decision depends on a load-bearing assumption that is not pinned down, the result is `UNDECIDABLE` with the pivotal assumption and the conditions under which the verdict would flip.

## Audit UI

The UI is intentionally built as an audit surface. It lets a reviewer:

- create a company workspace
- enter a natural-language proposal
- inspect Stage 1 questions and answers
- see the Stage 1 decision brief and unresolved notes
- trigger Stage 2 formalization
- inspect the proof draft, validation report, final verdict, derivation, binding constraints, assumptions, and refutation
- browse battery decisions and their verifier results

The UI does not try to hide weak premises. The intended reviewer workflow is to check the formal object first, then inspect the derivation and refutation.

## Assignment Outputs

The long-form outputs requested by the assignment are checked into `codex-resources/assignment-output`.

- [Battery verifier output](codex-resources/assignment-output/battery-verifier-output.md) contains verdicts, derivations, constraints, assumptions, and refutations for all 12 battery decisions.
- [Proposal pipeline output](codex-resources/assignment-output/proposal-pipeline-output.md) contains the interview transcript, formal object, and resulting verdict for proposals `P1` through `P6`.

The README links those artifacts instead of duplicating them because they are lengthy and easier to audit as separate files.

## Walkthrough

The primary end-to-end walkthrough case is `P3`, the brand-marketing runway proposal:

> "We've got $2M in the bank and we're burning $250k a month. Our board requires us to keep at least six months of runway at all times, no exceptions. I want to put $1M upfront into a brand-marketing campaign. Good idea?"

This case demonstrates the full flow:

1. Stage 1 asks for the expected monthly burn rate after the campaign.
2. The user answers `$300,000/month`.
3. Stage 2 computes post-spend cash of `$1,000,000`.
4. Stage 2 computes runway of `3.33` months.
5. The verifier refutes the decision because `3.33 < 6`, violating the hard runway constraint.

For an `UNDECIDABLE` trace, see `P1` in the proposal output or `D1` in the battery output. Those cases show the system declining to assert support when the proof depends on an unquantified productivity or objective-impact assumption.

## Models Used

Default models:

- Stage 1 interview: `google/gemini-2.5-flash`
- Stage 2 workspace proof draft: `google/gemini-2.5-pro`

The split is deliberate: Stage 1 needs a modest, fast model for elicitation and context management, while Stage 2 benefits from a stronger model for drafting structured proof material. The final checked result still depends on code validation and deterministic verification logic.

## What Was Cut

If I had more time, I most likely would've worked more on polishing Stage 2. The problem is that we could arrive at some kind of verdict, but it was a lot more difficult to construct a proof for the verdict. Even if there was a clear path, such as a contradiction between an assumption and a constraint, the model wouldn't be able to make those comparisons and computations with high confidence.

`decision_battery.json` also isn't the input for Stage 2. One of the biggest problems I encountered was converting the data from Stage 1 to fit the `decision_battery.json` schema. The reason was that the schema was too strict, and the model would hallucinate and try to categorize actions from a predefined set rather than staying AI-assisted.

There may also be small bugs within the frontend, just due to lack of time at the end of the project.

Not included:

- editable/toggleable assumptions in the UI
- a broad general-purpose business theorem prover
- full coverage for arbitrary constraint syntax
- automatic multi-company or multi-decision formalization from a single proposal

When the verifier does not implement a rule family or lacks required proof inputs, it returns `UNDECIDABLE` instead of filling the gap with a model judgment.

## AI Tool Usage

I chose to split the Stage 1 (interview) and Stage 2 (proof) models due to their speed and use cases. Stage 1 was mostly asking relevant questions and didn't need too much formatting, which is why I chose a lighter model like `gemini-2.5-flash`. However, Stage 2 required a lot more formatting because of the AST checker system and the need for computations and comparisons. I chose a larger model like `gemini-2.5-pro` so it would be able to handle the stricter formatting.

Codex assisted with implementation and documentation support. Final design choices, validation decisions, and submission framing were reviewed by me.