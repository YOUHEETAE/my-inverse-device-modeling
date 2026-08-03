# Multi-Case architecture

Stage 4 changes the Case Study screen from a single hard-coded topic into a
configuration-driven Case catalog. Stage 5 verifies the boundary with the
additional `oxide_gate_control` Case without mixing sessions or changing the
common learning flow.

## Runtime flow

1. `backend/learning/topics.py` validates and loads every JSON file in
   `backend/learning/configs`.
2. `CaseStudyPanel` builds its Case selector from that catalog.
3. Selecting a Case restores the most recently updated session for that
   `topic_id`, or creates a new session when none exists.
4. Session lists, reset, clone, rename, and delete remain scoped to the active
   `topic_id`.
5. The shared runner, state machine, analysis adapter, and tutor receive the
   selected `TopicConfig`; they do not select a Case themselves.

The most recently updated valid Case session is selected when the application
starts. Switching Case never deletes or resets the session of the Case being
left.

## Adding a Case later

Add one validated JSON file to `backend/learning/configs`. Its filename must
equal `topic_id`. Define:

- identity, description, and learning objectives;
- baseline and comparison experiment conditions;
- required model outputs;
- expected concepts and misconceptions;
- prediction and observation questions;
- allowed next actions; and
- theory concepts present in the shared theory knowledge base.

The Case then appears in the selector automatically. New Case content should
receive its own topic validation, runner, end-to-end learning, session
isolation, and tutor-quality regression tests before release.

## Current Cases

- `sce_channel_length`: Channel length 700 nm → 300 nm, with T fixed.
- `oxide_gate_control`: Gate oxide 20 nm → 10 nm, with L fixed at 700 nm.

A configuration is not considered a finished learning Case until its real
model directions, session isolation, question flow, Field claim limits, and
tutor grounding have dedicated regression coverage.
