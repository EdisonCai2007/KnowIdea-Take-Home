# Frontend Outline

## Purpose

This document outlines the first frontend pass for the proposal intake experience.
The target interaction should feel close to ChatGPT or Codex:

- a single main chat surface
- no chat history sidebar for now
- user messages in the main thread
- assistant-led clarification flow
- a bottom composer area
- one visible question at a time above the composer

This is a product outline only. It is not an implementation spec.

## Product Goal

The application should let a user:

1. create or confirm a company workspace
2. paste a proposal into a chat-style interface
3. answer AI clarification questions one at a time
4. complete the Stage 1 interview flow
5. view a result shell for later proof, derivation, and verification output

The experience should feel conversational rather than form-heavy.

## Core UX Direction

The UI should borrow the interaction pattern from ChatGPT and Codex, not the full product surface.

What to copy:

- central chat thread
- bottom-anchored input area
- assistant questions shown inline in the thread
- recommendation chips/buttons for fast replies
- an "Other" path where the user can type a custom answer
- progressive question flow that feels guided and lightweight

What not to include yet:

- left-side chat history
- multi-conversation management
- saved threads
- advanced settings panels
- final polished branding details

## High-Level Flow

### 1. Workspace Setup

The user first lands on a lightweight setup step for company context.

Fields:

- company name
- sector
- optional short description

Goal:

- establish the workspace context before proposal intake starts

Tone:

- simple, minimal, low-friction

Structure:

- this is a dedicated landing/setup screen
- the chat experience begins only after the company workspace is created

### 2. Proposal Submission

After workspace setup, the user sees the main chat screen.

Initial state:

- assistant introduces the flow
- user is prompted to paste or type a proposal
- the proposal input lives in the bottom composer area

User action:

- submit one proposal to begin the interview

Expected behavior:

- proposal appears as a user message in the chat thread
- assistant begins the clarification flow

### 3. Clarification Interview

This is the main interaction loop.

Desired frontend behavior:

- only one clarification question is visible at a time
- the active question appears above the composer area, similar to Codex
- each question includes:
  - the question prompt
  - three suggested answers
  - one clearly marked recommended answer
  - an "Other" option that allows a typed custom response

User interaction pattern:

1. assistant shows the current question
2. user selects a recommended answer or types a custom answer
3. if the user clicks a suggested answer, it populates the composer first rather than submitting immediately
4. user sends the final answer from the composer
5. answer is added to the conversation
6. the user may move back to earlier questions within the current backend batch and edit those answers before batch submission
7. the batch UI should expose this with simple arrow-based previous/next controls
8. frontend advances to the next question in the current batch
9. only after all questions in the current batch are answered does the frontend send the batch back to the backend

Important backend-alignment note:

- the current backend can return up to three clarification questions at once
- the frontend should still reveal them sequentially, one at a time
- the UI should feel single-question driven even when the backend response is batched

### 4. Completion State

Once Stage 1 is ready, the question flow ends and the UI transitions to a result shell.

This should still feel like part of the same conversation, not a separate tool.

## Main Screen Areas

### Chat Thread

The main thread should contain:

- assistant intro copy
- the user proposal
- assistant clarification questions
- user answers
- completion summary content

The thread should read as a clean conversation, not as a stacked form.

### Active Question Zone

This is the most important interaction area during the interview.

It should sit just above the bottom composer and contain:

- the current assistant question
- a visible progress label such as "Question 1 of 3"
- the three suggested answers as quick actions
- the recommended answer clearly emphasized
- an "Other" path for custom text entry

Only one active question should be shown at a time.

### Composer Area

The bottom composer should support two modes:

- proposal submission mode at the beginning
- custom-answer mode during the clarification flow

The composer should remain visually stable across both modes so the app feels consistent.
Suggested answers should populate the composer, not bypass it.

## Conversation Behavior

### Proposal Phase

- user enters proposal text
- submit action starts the interview
- assistant acknowledges and moves into clarification

### Question Phase

- assistant controls the flow
- user answers one question at a time
- quick replies should reduce typing when possible
- custom input should remain available when the suggestions do not fit

### Completion Phase

- assistant stops asking questions
- the interface shifts from intake to outcome display
- the result experience should remain embedded in the conversation so the chat itself starts to feel more dashboard-like rather than switching to a separate dashboard page

## Result Shell

For now, the post-interview screen should include a full shell for later output, even if the detailed content evolves later.

Sections to reserve:

- Stage 1 readiness summary
- current decision brief / derived understanding
- derivation or proof area
- constraints / assumptions area
- verification status
- follow-up notes or unresolved items

At this stage, this section is structural only.
Earlier conversation history should remain visible and scrollable above the result content.

## UX Principles

- Keep the experience conversational.
- Reduce visible complexity.
- Prefer progressive disclosure over dense forms.
- Make the recommended path obvious without blocking custom input.
- Keep the user focused on the single current question.
- Preserve continuity between intake, clarification, and results.
- Push the visual language toward KnowIdea identity rather than staying too close to ChatGPT/Codex neutrals.

## States To Account For

### Empty State

- workspace not set up yet

### Ready To Start

- workspace exists
- no active proposal yet

### Interview In Progress

- proposal submitted
- clarification questions active

### Waiting / Processing

- answers for the current batch have been completed
- frontend is waiting for the next backend response
- Stage 1 loading copy should read `Planning...`
- Stage 2 loading copy should read `Thinking...`

### Stage 1 Ready

- no more clarification questions
- completion summary available

### Result View

- result shell displayed with placeholders for proof and verification details

### Error State

- if the backend errors during the flow, keep the conversation intact
- show a small inline error treatment
- do not add a retry button in this pass

## Content Priorities

During the clarification stage, the frontend should emphasize:

- the current question
- the three suggested answers
- the ability to provide a custom answer
- the sense of moving forward step by step

It should not emphasize:

- raw backend data
- developer-facing terminology
- large JSON blocks
- dense diagnostic panels

## Out Of Scope For This Pass

- chat history sidebar
- multiple proposal threads
- exact visual design system
- final copywriting polish
- finalized proof-detail presentation
- frontend implementation
- backend contract changes
- mobile-specific optimization work

## Current Assumptions

- the existing workspace setup concept remains part of the product flow
- company setup is a dedicated landing screen before chat begins
- the frontend will sit on top of the current Stage 1 proposal interview behavior
- backend question batches may contain up to three questions
- the frontend should reveal those batched questions sequentially
- the backend call should happen after the full current batch is answered
- users can move backward within the current batch and edit prior answers before submission
- suggested answers populate the composer first and are not auto-submitted
- there is no per-question skip or "I'm not sure" action in this pass
- the result shell should exist now even if its detailed content is defined later
- the result shell remains within the chat thread and should feel conversational with dashboard-like density
- prior history remains visible and scrollable
- editing the original proposal after interview start is not supported; users must restart
- mobile is not a priority for this pass
- the visual direction should lean toward KnowIdea identity
- loading copy uses `Planning...` for Stage 1 and `Thinking...` for Stage 2
- backend errors should appear as small inline errors without retry controls
