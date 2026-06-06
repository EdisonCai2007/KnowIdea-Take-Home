# Frontend Phases

## Phase 1: Workspace Gate + Chat Shell

- Replace the current landing layout with a dedicated workspace setup screen for company name, sector, and optional description.
- Shift the app into a chat-style interface after workspace creation, with one main thread, no sidebar, and a stable bottom composer.
- Apply the KnowIdea visual direction through a glass header, stronger typography, atmospheric background treatment, and cleaner message surfaces.

## Phase 2: Proposal Intake + Clarification Flow

- Use the bottom composer for both initial proposal submission and later clarification answers so the interaction stays consistent.
- Render the proposal and assistant responses as a conversation instead of a stacked form or diagnostic panel.
- Reveal backend clarification batches one question at a time, even when up to three questions are returned together.
- Add progress copy, previous/next batch navigation, suggestion chips, a clearly marked recommended answer, and an `Other` path through normal typed input.
- Keep answers editable within the current batch and submit the full batch only after all visible questions are answered.

## Phase 3: Completion + Result Shell

- Keep the conversation visible after Stage 1 completes and append an embedded result shell instead of switching to a new page.
- Show a structured summary first: readiness summary, derived understanding, assumptions or constraints, verification status, and follow-up notes.
- Keep Stage 2 proof and verification details available but visually secondary so the result area feels product-facing rather than raw or technical.
- Preserve inline loading and error states within the same thread, using `Planning...` for Stage 1 activity and `Thinking...` for Stage 2 activity.

## Defaults

- No backend contract changes in this pass.
- No frontend framework migration in this pass; the work stays on the current web surface.
- No chat history, multi-thread management, advanced settings, or finalized proof-detail design in this file’s scope.
