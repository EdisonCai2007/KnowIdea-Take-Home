# Project Decisions

Captured from planning discussion on June 5, 2026.

- Submission priority: `Score-first`
- Preferred stack: `Python + simple web UI`
- Stage 1 behavior: `Strict clarifying flow`
- Audit UI scope: `Required only`

## What This Means

The deterministic verifier is the center of gravity for this project, since verifier correctness and conservative reasoning drive the score. The UI should stay plain and audit-focused, and the system should ask for missing premises rather than inventing them.
