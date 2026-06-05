# Take-Home: The Decision Prover

**Time budget:** up to 24 hours from when you open this.
**Deliverable:** a two-stage system (an LLM that **interviews + formalizes**, feeding a **verifier**) + a simple audit UI + a README + a walkthrough.
**Provided:** `decision_battery.json` and `nl_proposals.md` (your two evaluation inputs), and an **OpenRouter API key with a $20 budget**.

---

## The idea

In mathematics, *autoformalization* is the project of taking an informal claim — something a human wrote in prose — and translating it into a formal statement a machine can actually **verify**. Two things have to happen: the messy translation (natural language → formal object), and the checking (does the formal claim hold). The translation is the hard, unsolved part; the checker, once you have a formal statement, is comparatively mechanical.

We want you to port that whole arc to business decisions.

You'll build a system that takes a **proposed business decision in plain language**, works with the user to pin it down, **formalizes** it into a structured object (facts, hard constraints, stated assumptions), and then **proves, refutes, or declares it undecidable** — producing an auditable argument a skeptic can inspect. Natural language in; a checked verdict, with its reasoning exposed, out.

### Read this part twice

A proof here is **not** a proof that the decision is *good*. Business has no axioms that are true by construction; "we should expand to Europe" can follow validly from premises that are themselves wrong. What your system can honestly establish is **validity relative to a stated context**: given these facts, these constraints, and these assumptions, does the decision follow, and *which assumptions is the conclusion standing on*.

That reframe runs through both stages. A good system is honest **twice**: when it formalizes, it refuses to invent premises the user never gave (it asks instead); when it verifies, it refuses to manufacture a proof that doesn't exist (it says so instead). The thing we're testing, end to end, is whether you can build something that stays honest under pressure to just say yes. **The interesting, load-bearing work is the formalizer's willingness to ask and the verifier's willingness to refuse.**

---

## What your system does — two stages

### Stage 1 — Interview & formalize (LLM)

Take a natural-language proposal. Most real proposals are under-specified — "we should hire a few more engineers" omits how many, at what cost, against what runway. Your system's job is to **surface what's missing and ask for it**, then translate the result into the structured schema below.

The single most important behavior here: **elicit, don't fabricate.** When a quantity the formalization needs isn't stated, a weak system quietly invents a plausible number and produces a confident-but-fictional formal object. A strong one notices the gap and asks the user — *how many, at what fully-loaded cost, what's your cash and burn, is there a runway or budget constraint?* Treat a missing premise the way the verifier treats a missing proof step: as something to flag, not paper over. Resisting a user who is pushing for a particular answer is part of the test.

The output of Stage 1 is a structured object: typed **facts** (with values and units), **hard constraints** (with a checkable semi-formal expression), and **assumptions** (tagged as `given` vs. `projected`). The schema is exactly the one used in `decision_battery.json` — study that file; it is both your Stage-2 input *and* your formalization target.

### Stage 2 — Verify

Given a structured object (either one your Stage 1 produced, or one handed to you directly), emit a verdict in one of three classes:

- **SUPPORTED** — there is a valid derivation, from the stated facts and assumptions, showing the decision satisfies every hard constraint *and* meets its stated objective.
- **REFUTED** — the decision provably violates a hard constraint, or its negation is provable (an available alternative strictly dominates it on the stated objective).
- **UNDECIDABLE** — the verdict depends on a load-bearing assumption the facts don't pin down: SUPPORTED under one reading, REFUTED under another. The honest move is to name that pivotal assumption (ideally the threshold at which the verdict flips) and decline to assert a proof.

One precedence rule, because it's where naive systems fail: **a hard-constraint violation refutes a decision no matter how attractive its projected returns are.** Check feasibility before optimality.

Alongside the verdict, Stage 2 must produce: **(1) a derivation** — an ordered sequence of steps, each stating the rule applied, its inputs, and its result; **(2) the binding constraints** it checked, each marked pass/fail with a reason; **(3) the load-bearing assumptions** the verdict rests on; and **(4) a refutation attempt** — the system should actively try to *break* the decision, searching for a counterexample or the conditions under which it fails, and report what it found. The refutation is in scope, not optional; a decision that survives a genuine attempt to break it is worth far more than one merely asserted.

### Semi-formal, by design

We are not asking for a full theorem prover or for all of business encoded in logic. We want a **semi-formal** system: a defined schema for premises, constraints, and inference steps, with **programmatic checking** of the things that can be checked (constraint satisfaction, arithmetic and unit-economics steps, dominance), and the LLM doing the translation and explanation around it. Where you draw the line between "checked by code" and "decided by a model" is one of the most important decisions in this assignment — make it deliberately and defend it in the README. The inference vocabulary you'll need is small and standard: unit economics (LTV, CAC, payback), cash-flow and runway projection, constraint propagation, expected value, and dominance arguments cover everything in both input sets.

---

## Your two evaluation inputs (they test different stages)

- **`decision_battery.json` — 12 already-formalized decisions.** These are handed to you in the structured schema, so they exercise **Stage 2 in isolation**. Run your verifier directly over them; do not re-formalize them. This is the objectively scored core (see below). It's also your worked reference for what a clean formal object looks like.
- **`nl_proposals.md` — raw natural-language proposals.** These have *not* been formalized. They exercise **Stage 1 and the end-to-end pipeline**: your system must interview, formalize, then verify. Some are deliberately under-specified to see whether you ask or invent.

---

## Two worked micro-examples (neither is from the inputs)

**Stage 1 — a formalization turn.** User: *"Should we spend a bit on a conference booth?"* A good system does not invent a number; it asks: *"What's the booth cost, your current cash balance, and any minimum-cash policy I should respect?"* Given *"$50k; we have $100k; never go below $80k,"* it emits:
`facts: {cash: 100000, booth_cost: 50000}` · `constraints: [{id: reserve_floor, semi_formal: "cash(t) >= 80000 for all t"}]` · `action: {spend: 50000}`.

**Stage 2 — the verdict on that object:**

```
classification: REFUTED
derivation:
  1. rule: apply_cash_outflow | inputs: cash=100000, outflow=50000 | result: cash_after = 50000
  2. rule: check_constraint   | inputs: cash_after=50000, floor=80000 | result: 50000 < 80000 -> violated
binding_constraints:
  - {id: reserve_floor, pass: false, why: "post-spend cash 50000 < 80000 floor"}
load_bearing_assumptions: []
refutation: {attempted: true, failure_conditions: "violation is unconditional; no assumption rescues it"}
```

What makes this a *proof* and not a vibe: the formalizer asked instead of guessing, every step has a rule and inputs, and the conclusion is forced by the numbers. Your real outputs should have the same character — even when the right answer is "I need more information" or "I cannot decide this."

---

## The audit UI

A proof you can't inspect is just a verdict with extra steps. The third piece of the deliverable is a **simple UI whose only job is to let a skeptical human audit the system** — both what it *extracted* and what it *concluded*. We are explicitly asking for clarity, not chrome: a plain, legible interface that makes the argument inspectable beats a beautiful one that hides it.

In rough priority order, the UI should:

1. **Show the formal object the system extracted** — the facts, constraints, and assumptions it built from the conversation — so a human can catch a bad *formalization* before judging the proof. A wrong premise is as fatal as a wrong inference, and this is where you'd catch it.
2. **Render the derivation as a structure, not a paragraph** — the ordered steps, each with rule, inputs, and result, followable link by link. Expandable steps (drill from "constraint failed" to the exact numbers) beat a flat dump.
3. **Make the verdict traceable to its cause** — for REFUTED, the violated constraint is what the eye lands on; for UNDECIDABLE, the pivotal assumption (and flip threshold) is front and center.
4. **Surface the load-bearing assumptions as first-class objects** — at a glance, which premises the whole conclusion rests on.

**Stretch goal (reach for this only once the above is solid):** make the UI an *instrument*, not a report — let the auditor **toggle or edit an assumption and watch the verdict change.** Several proposals and battery items are UNDECIDABLE precisely because they flip at a specific threshold; a UI where you push an assumption past that line and watch SUPPORTED turn into REFUTED is the demo that makes this whole idea click. It's hard to do well in the time, which is why it's a stretch and not a requirement.

---

## How we score it

The verifier is the part we grade hardest, and it has an objective metric. The formalizer is graded on a rubric, because honest formalization is the harder behavior to fake.

### Part A — the verifier (objective, on `decision_battery.json`)

**Primary — classification accuracy**, with a deliberate asymmetry. A correct verdict is full credit. Asserting a definite verdict (SUPPORTED or REFUTED) when the honest answer is UNDECIDABLE scores **zero** — claiming a proof that doesn't exist is the failure this exercise exists to catch. Answering UNDECIDABLE when a definite verdict was available is a partial-credit miss: over-caution is real but safer than confident error. We read the full confusion matrix; a system that *never* returns UNDECIDABLE is a tell regardless of accuracy.

**Secondary — did it catch the specifics.** For constraint-refuted items, did it name the *actual* violated constraint? For undecidable items, did it identify the *correct* pivotal assumption, and (a distinguishing signal) the threshold at which the verdict flips?

**The rubric that matters most — derivation soundness.** Are the steps valid, or post-hoc rationalizations dressed up as logic? Does it check feasibility before optimality? When it can't prove something, does it emit "no valid proof exists" as a first-class result rather than manufacturing one? Is the refutation real or decorative?

### Part B — the formalizer (rubric, on `nl_proposals.md`)

**Elicitation over fabrication** is the headline criterion: when a proposal omits something the formalization needs, does your system *ask*, or does it invent a number and march on? Show us the interview. Then: is the resulting **formal object faithful** to what the user actually said (right facts, right constraints, no hallucinated premises, and noise correctly ignored)? Does it hold up under a user who is pushing for a particular answer? For the proposals that contain enough information to reach a verdict, does the **end-to-end** pipeline land on the right one?

### Across both — legibility, and honesty over agreeableness

Could a reasonable skeptic use your UI to find the load-bearing assumption and the step that settles the case, without reading your code? We score legibility of the argument, not visual polish — and we will not reward a polished UI on a weak verifier. **A submission that lands the right answers on rationalized reasoning scores below one with slightly worse accuracy and visibly sound, auditable reasoning at both stages.** The system's value is that it can say "I don't have enough to decide" and "the facts don't support this." Build for that.

---

## What we provide, and what you'll need

You'll receive: the two input files above; an **OpenRouter API key with a $20 budget**; and the logistics block at the bottom of this doc.

About the key: $20 is ample — the in-system model runs over a dozen decisions and a handful of proposals, so real usage is a few dollars; the cap is just a guardrail against a runaway loop. Use **any model available on OpenRouter**; pick a modest one, and tell us which in the README. The LLM is a **required** part of the system for Stage 1 (the interview and formalization) — that's the natural-language-to-formal step the assignment is about. Using AI **coding** assistants (Cursor, Copilot, Claude Code, etc.) to write your code faster is a separate thing, entirely encouraged, and runs on your own machine — just tell us how you used them.

One hard requirement on runnability: **we must be able to run your system using only the key we provide.** If your system needs an API key, it should read the one we supply (document the env var in your README). Don't ship something whose grading run depends on a private account we don't have.

---

## Ground rules

Use any stack. Keep any in-system model to a single, modest choice, and make the **verification do real work** rather than delegating the judgment to a black box — "the model said REFUTED" is not a derivation; the model proposes structure and prose, your checker decides. Scope ruthlessly: a system that does the interview-formalize-verify loop *well* on a narrower set of inference rules beats one that sprawls and rationalizes. If you cut something, tell us what and why.

## What to submit

1. **The code** (repo or zip) and how to run it from nothing, reading the provided key.
2. **Verifier output on the battery** — verdict, derivation, constraints, assumptions, refutation for all 12 decisions, in any clear format.
3. **Pipeline output on the proposals** — for each, the **interview transcript**, the **formal object** your system produced, and the resulting **verdict**.
4. **A README** covering: your formalization schema and inference rules; how the interview decides what to ask; where you drew the code-vs-model line and why; how refutation works; which OpenRouter model you used; a sentence on what the audit UI lets a user do; what you cut; and how you used AI tools.
5. **A walkthrough** — drive one **end-to-end** case through the UI: a vague proposal, your system asking for what's missing, the formal object it builds, and the checked verdict. Include at least one UNDECIDABLE result and show how a skeptic would trace it. Take as long as you need.
