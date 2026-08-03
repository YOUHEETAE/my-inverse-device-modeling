# Learning Tutor Core

The Tutor Core uses a two-stage LLM pipeline around Python-owned scientific
controls. It is shared learning infrastructure rather than a list of expected
questions and canned answers.

## Two-stage question pipeline

For a connected external provider, a free-form question follows this sequence:

1. The Intent Interpreter receives the question, recent conversation, Case
   description, allowed concepts, metrics, parameters, and actions. It does not
   receive simulation values and returns structured JSON only.
2. Python validates all concept/metric IDs, rejects invented condition values,
   resolves conversation references, and makes the authoritative route and
   experiment/action decision.
3. Python retrieves theory and builds a minimal evidence bundle from verified
   simulation results.
4. The Answer Writer receives the confirmed intent, answer plan, retrieved
   theory, and evidence bundle and writes cohesive Korean in the requested
   structure.
5. Python validates route identity, evidence IDs, numbers, experiment flags,
   and suggested actions before display.

If the Intent Interpreter returns semantically invalid JSON, Python may
reconstruct the route and continue to the external Answer Writer. If the
configured external provider is unavailable, a network/provider call fails, or
the final answer cannot pass validation, the public workflow returns an
actionable `external_error`; it does not substitute a deterministic local answer
as though it came from the LLM. The saved turn retains only the sanitized route,
retry, and checkpoint state required to continue safely.

## Resilient interpretation and failure isolation

The intent contract describes meaning rather than exact wording. In addition to
the primary intent, it carries the utterance type, confidence, alternative
intents, requested answer structure, and conversation-reference flags. Common
provider variations in intent/action/metric names, omitted optional flags,
numeric condition strings, and empty clarification fields are normalized before
validation. Unknown concepts or condition values that were not present in the
question are still rejected.

Python treats explicit experiment facts and result references as authoritative.
For example, `이 실험은 700과 300 nm만, 즉 길이만 바꾼 거 맞잖아` is handled
as confirmation of the current controlled comparison, not as an unrelated
question or a request to run another experiment. The response can cite
`experiment:conditions`, which contains the changed and fixed conditions.

Recovery is isolated by pipeline stage:

- if intent JSON is semantically invalid, Python reconstructs the route and
  still sends the grounded answer plan to the Answer Writer;
- provider, authentication, network, timeout, and rate-limit failures stop the
  external pipeline with stage-specific retry guidance;
- if the Answer Writer fails validation, a bounded repair may be attempted and
  a remaining failure becomes `external_error`.

Transient response diagnostics can distinguish “Python repaired the
interpretation” from an external answer failure for operator investigation.
Before session persistence, raw warnings and `fallback_detail` are removed; the
GUI renders only a learner-safe error category, retry action, wait time, and
preservation state.

## Learner claims, corrections, and feedback

Free-form input is also treated as a learning dialogue move, not only as a
question. `LearningResponsePlan` converts the validated utterance type and
route into one of the following Python-owned strategies:

- answer a question;
- evaluate a learner claim;
- acknowledge a correction;
- confirm the current experiment setup;
- clarify ambiguous meaning;
- separate a prediction from an observed result.

For a claim, correction, or confirmation, the Answer Writer must first state
what is supported, correct only the unsupported portion, and then continue the
physical explanation. It returns a structured `claim_assessment`,
`acknowledged_points`, `correction_points`, and an optional
`next_learning_question`. Python validates these fields and requires current
result evidence before accepting a supported or contradicted result claim.
The deterministic answerer used by offline audits and tests follows the same
response plan. It is not automatically substituted into the public chat when a
configured external provider fails.

The resulting claim record is stored in `DialogueState.student_claims` with its
concepts, assessment, evidence IDs, accepted points, and corrections. The last
three records are supplied to the next answer plan, so a later question can
build on a correction instead of repeating the previous mistake. These records
survive session save, close, and restore. The Case Study chat marks claim
feedback and displays the optional next learning question separately.

## Adaptive explanation level

The free-question pipeline uses a bounded learner profile assembled from the
session's understanding level, completed learning targets, remaining targets,
and detected misconceptions. It also maintains per-concept mastery derived
only from assessed learner claims. Merely showing an explanation does not mark
a concept as mastered.

`LearningResponsePlan` maps this profile to one of three delivery levels while
leaving the scientific route, knowledge layers, evidence IDs, and allowed
actions unchanged:

- `foundational`: introduce the core term and use a short
  cause→mechanism→result chain;
- `intermediate`: reduce definition repetition and connect observations to
  physical mechanisms;
- `advanced`: emphasize condition dependence, validation, and transfer to a
  new controlled comparison.

A stored misconception takes priority over a nominally high understanding
level and selects a diagnostic correction flow. An explicitly concise request
still limits the detail budget. The server records the selected
`explanation_level` and `adaptation_reasons` on every turn, and produces a
level-appropriate concept check, mechanism check, diagnostic question, or
transfer question when the writer does not provide one. Deterministic
audit/test answers use the same plan. The GUI displays the selected explanation
level so the adaptation is visible rather than hidden.

## Tutor quality audit

`quality_audit.py` evaluates a completed conversation without asking an LLM to
judge another LLM. Each turn is checked against server-owned contracts:

- valid route and a non-empty, non-duplicated answer;
- verified evidence for current-result turns;
- no result evidence in theory, hypothetical, or out-of-scope turns;
- an explicit new-experiment boundary for predictions;
- assessment, acknowledgement, and evidence for learner claims;
- persisted adaptive-level metadata and a level-appropriate continuation;
- safe provider-failure state and intent-recovery metadata.

Scenario inputs are JSON data rather than Python question matching code. A
future Case can therefore supply its own topic ID, analysis fixture, learner
profile, questions, and expected routes while reusing the same runner and
quality gates. `tools/tutor_quality_audit.py` prints a strict JSON report and
returns a non-zero exit code when a scenario or quality gate fails. The actual
model-backed Case smoke also runs this audit after session save/restore.
Detailed quality and failure counters remain test/operator information rather
than learner-facing provider diagnostics.

## Routing contract

`TutorQuestionRouter` produces a server-owned `QuestionRoute` with:

- `question_type`: current result, Case theory, adjacent theory, hypothetical,
  new experiment, or out of scope;
- `relevance_to_case`: direct, related, domain-adjacent, or unrelated;
- matched semiconductor concepts;
- whether current simulation evidence may be used;
- whether clarification or a new experiment is required;
- whether the concepts were inherited from conversation history.

The external LLM receives this route but cannot change it. A mismatched route,
an unknown evidence ID, or a current-result number without evidence triggers
one bounded repair request and then a learner-safe `external_error`.

## Conversation context

Each session now owns a versioned `DialogueState` instead of relying only on a
sliding window of raw turns. It stores the current topic and focus, referenced
result, last explained concept, pending clarification, open experiment request,
last interpreted intent, and reserved student-claim memory. Each persisted
follow-up updates this semantic state. Questions such as `그건 왜?` can therefore
inherit the previous concept after the application is restarted. Sessions saved
before this schema was added rebuild the state from their follow-up history.

## Knowledge authority layers

The answer pipeline receives four explicitly separated layers:

1. `experiment_facts`: baseline/comparison conditions, changed parameters,
   fixed parameters, and controlled-comparison status;
2. `result_facts`: verified before/after values, direction, units, and evidence
   IDs;
3. `metric_definitions`: the exact Curve bias and extraction method used by
   this repository;
4. `theory_facts`: general semiconductor principles and Case connections.

Metric definitions are exported by
`tcad/data_extraction/parameter_extraction_core.py`, which is also used for the
actual calculation. This prevents the learning explanation from drifting away
from the implemented Ion, Ioff, Vth, SS, DIBL, gm, gds, Ron, and λ definitions.
The same definition layer is available to deterministic offline audits and
tests. A provider failure is reported for retry rather than being replaced by a
generic textbook answer.

## Extension boundary

The router accepts a configurable concept-alias mapping. A future Case supplies
its topic contract and analysis context; it does not add a separate question
matching function. Theory retrieval and broader answer generation are separate
layers built on this routing contract.

## Shared theory knowledge

`knowledge/semiconductor_theory.json` stores atomic concepts rather than
question-answer pairs. Each concept contains a summary, principles, general
effects, related concept IDs, Case connection, and caveats. The graph retriever
starts from the route's matched concepts and adds only their direct relations.

The deterministic answerer used by offline audits and tests composes:

- verified metric changes and evidence IDs for current-result questions;
- summaries and principles for Case or adjacent theory;
- general effects, caveats, and an explicit experiment boundary for
  hypothetical conditions;
- clarification plus useful theory when terminology is ambiguous.

The same retrieved theory is supplied to the external LLM. The LLM route remains
server-owned, and retrieved theory IDs and Case connection are attached to the
validated response and persisted with the conversation.

Each Case config declares its shared `theory_concepts`. Topic loading rejects
unknown IDs, so adding a future Case requires configuration rather than a new
question-specific routing function.

## Provider diagnostics and request inspection

An external-provider failure may retain the pipeline stage, HTTP status,
provider error message/type/code, UTF-8 request size, model, request ID, and
safe rate-limit headers in transient operator diagnostics. API keys and
authorization headers are never retained. Before a Case Study session is
saved, diagnostics are reduced to the failure category, pipeline stage, HTTP
status, retry delay, and whether an intent checkpoint is available. Raw
provider messages, model names, request sizes, headers, request IDs, and
fallback details therefore do not reappear after a session is reopened.

When the Case Study is configured to use Groq and a free-question call fails,
the chat does not substitute a local theory answer. It returns an
`external_error` turn rendered through the public-presentation boundary. The
learner sees a plain-language category, whether retrying can help, a recommended
retry delay, and whether the question or checkpoint was preserved. The raw
provider message and identifiers remain internal. HTTP 429 uses the provider's
retry timing with a rolling-window safety margin. HTTP 413 explains that waiting
cannot fix an individually oversized request; authentication, timeout, network,
validation, and server errors receive separate recovery guidance. The failed
question is persisted but excluded from learning mastery, semantic turn count,
and the history sent on the next retry.

HTTP 429 is not retried immediately inside the provider. If the first intent
call succeeded and the answer call was rate-limited, that validated intent is
stored as a retry checkpoint. Sending the exact same question again reuses the
checkpoint and calls only the answer writer. In that case the displayed wait is
the provider's `retry-after` plus a one-second boundary margin. If no checkpoint
exists, the guidance uses the full token-reset interval because the complete
two-stage pipeline must run again.

The exact two-stage request for a saved session can be reconstructed without
calling Groq:

```powershell
python tools\inspect_tutor_request.py --question 'Ioff는 어떤 파라미터야?'
```

Add `--full` to include the complete system prompt, user prompt, and structured
payload. The report includes each payload section's UTF-8 byte size and an
example of the JSON contract expected from each stage.

The answer writer uses a question-scoped Context Pack. It keeps the requested
metric definitions, verified result facts, relevant observations, theory
mechanisms, caveats, and Case connections while removing duplicate full-session
snapshots. Independent definition questions do not carry unrelated curve or
field evidence; context-dependent corrections and follow-ups keep the necessary
recent turn and student claim. The resulting follow-up prompt has a conservative
16.5 KB UTF-8 budget for the Groq free-tier pipeline. If a broad multi-metric
question exceeds it, optional graph-neighbour detail and action descriptions are
reduced before any requested metric definition or verified result fact.

## Single-Case final validation

`tools/case_study_smoke.py` runs the actual 700 nm/300 nm models and verifies:

- prediction, simulation, observation feedback, and Case completion;
- current-result questions and context-inheriting follow-up questions;
- Case theory, adjacent theory, hypothetical conditions, new experiments, and
  out-of-scope routing;
- evidence IDs for current results and separation from general theory;
- JSON session restore of analysis results and question metadata.

External-LLM success, timeout, and invalid-response paths use deterministic test
providers, so fallback behavior is verified without requiring a network call or
an API key. A live Groq connection remains an environment-level smoke check.

Run the fast deterministic tutor audit with:

```powershell
python tools\tutor_quality_audit.py
```
