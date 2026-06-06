# Decision Prover

Phase 4 adds an optional OpenRouter-backed second-opinion layer on top of the deterministic Stage 2 verifier. The verifier still owns the authoritative verdict, derivation, constraint checks, assumptions, and refutation output. The model now produces its own independent advisory classification from the normalized decision context.

Workspace proposals also use an OpenRouter-backed Stage 2 formalization step after `stage1_ready`. That handoff converts the Stage 1 brief, transcript, and answers into a single-company, single-decision `DecisionBattery` document before the deterministic verifier runs.

## Setup

1. Install the project dependencies.
2. Copy `.env.example` to `.env`.
3. Paste the provided OpenRouter key into `OPENROUTER_API_KEY`.

Environment variables:

- `OPENROUTER_API_KEY`: required for Stage 2 workspace formalization and AI explanation surfaces
- `OPENROUTER_MODEL`: defaults to `google/gemini-2.5-flash-lite`
- `OPENROUTER_BASE_URL`: defaults to `https://openrouter.ai/api/v1`
- `OPENROUTER_TIMEOUT_SECONDS`: request timeout in seconds, defaults to `30`

## Code vs Model Boundary

### Workspace Stage 2 formalization

- The model converts a `stage1_ready` workspace proposal into one valid `DecisionBattery` document with exactly one company and one decision.
- The formalizer is omission-first: if a proof-bearing field is not grounded in the proposal, answers, or Stage 1 summary, it should be omitted rather than invented.
- Sparse but valid outputs are acceptable. Empty `facts`, empty `constraints`, partial typed actions, and generic action payloads are allowed when they are the most faithful representation.
- The formalizer should preserve unresolved load-bearing unknowns as explicit assumptions when grounded, instead of faking complete numeric inputs.
- Code validates the formalized battery, checks one-company/one-decision identity rules, and then runs a non-blocking grounding audit over emitted proof fields.
- Missing grounding entries do not fail Stage 2 by themselves. They are surfaced back through `formalization.notes` as warnings so the UI can expose what remains weakly grounded.

### Deterministic verifier and AI explanation

- Code decides `SUPPORTED`, `REFUTED`, or `UNDECIDABLE`.
- Code produces the canonical `derivation`, `binding_constraints`, `load_bearing_assumptions`, and `refutation`.
- The OpenRouter model receives only the normalized `DecisionContext`, not the deterministic verifier result.
- The model returns an independent advisory verdict using the same three labels: `SUPPORTED`, `REFUTED`, or `UNDECIDABLE`.
- The explain surface returns both the deterministic code result and the independent AI result, plus a simple `comparison` field showing whether they match.
- The AI result never feeds back into the deterministic proof or changes the authoritative verdict in Phase 4.

## Explain Surfaces

Existing verifier surfaces remain stable:

- `decision-prover verify run --input ... --decision-id ...`
- `GET /api/verify/{decision_id}`

New opt-in explanation surfaces:

- `decision-prover verify explain --input ... --decision-id ...`
- `GET /api/verify/{decision_id}/explain`

If `OPENROUTER_API_KEY` is missing, the explain command fails fast and the explain API returns a configuration error. If the model call fails or returns invalid JSON, the explain response still returns the deterministic verifier result with `ai_status="error"` and `comparison="ai_error"`.

## Testing

Run the full test suite:

```bash
pytest
```

Manual phase-four checks:

```bash
decision-prover verify run --input codex-resources/original-project-specs/decision_battery.json --decision-id D1
decision-prover verify explain --input codex-resources/original-project-specs/decision_battery.json --decision-id D1
decision-prover ui serve
```

Then compare:

- `GET /api/verify/D1`
- `GET /api/verify/D1/explain`

OpenRouter smoke tests by verdict:

```bash
bash scripts/openrouter_smoke_test.sh supported
bash scripts/openrouter_smoke_test.sh refuted
bash scripts/openrouter_smoke_test.sh undecidable
bash scripts/openrouter_smoke_test.sh all
```

These map to representative battery cases:

- `D2` -> `SUPPORTED`
- `D3` -> `REFUTED`
- `D1` -> `UNDECIDABLE`

If you want the raw underlying commands instead of the helper script:

```bash
decision-prover verify explain --input codex-resources/original-project-specs/decision_battery.json --decision-id D2
decision-prover verify explain --input codex-resources/original-project-specs/decision_battery.json --decision-id D3
decision-prover verify explain --input codex-resources/original-project-specs/decision_battery.json --decision-id D1
```

## OpenRouter Model

The default explanation model is `google/gemini-2.5-flash-lite`, pinned through `OPENROUTER_MODEL` unless explicitly overridden.
