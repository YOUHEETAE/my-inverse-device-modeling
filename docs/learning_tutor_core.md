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

If either LLM stage fails, the deterministic router and grounded local answerer
remain available. The persisted turn records the interpreted intent as well as
the final route and evidence.

## Resilient interpretation and staged fallback

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

Fallback is isolated by pipeline stage:

- if intent JSON is semantically invalid, Python reconstructs the route and
  still sends the grounded answer plan to the Answer Writer;
- provider/network failures use the deterministic router and local answerer;
- if the Answer Writer fails validation, only that stage falls back locally.

The turn persists `interpretation_source`, `pipeline_warnings`,
`fallback_reason`, and a safe `fallback_detail`. The GUI can therefore
distinguish “Python repaired the interpretation” from “the final answer fell
back locally” instead of showing every failure as a generic Groq error.

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
The local answerer follows the same response plan when the provider is
unavailable.

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
transfer question when the writer does not provide one. The local fallback
uses the same plan. The GUI displays the selected explanation level so the
adaptation is visible rather than hidden.

## Tutor quality audit

`quality_audit.py` evaluates a completed conversation without asking an LLM to
judge another LLM. Each turn is checked against server-owned contracts:

- valid route and a non-empty, non-duplicated answer;
- verified evidence for current-result turns;
- no result evidence in theory, hypothetical, or out-of-scope turns;
- an explicit new-experiment boundary for predictions;
- assessment, acknowledgement, and evidence for learner claims;
- persisted adaptive-level metadata and a level-appropriate continuation;
- visible diagnostics for provider fallback and intent recovery.

Scenario inputs are JSON data rather than Python question matching code. A
future Case can therefore supply its own topic ID, analysis fixture, learner
profile, questions, and expected routes while reusing the same runner and
quality gates. `tools/tutor_quality_audit.py` prints a strict JSON report and
returns a non-zero exit code when a scenario or quality gate fails. The actual
model-backed Case smoke also runs this audit after session save/restore. In the
GUI, the free-question header shows passed turns, fallback count, and any turns
that require inspection.

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
one repair request and then the local fallback.

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
The same definition layer is available to the local fallback, so a provider
failure does not reduce a question such as `Ion은 언제의 전류야?` to a generic
textbook definition.

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

The local answerer composes:

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
& 'C:\Users\T590\anaconda3\envs\devsim_env\python.exe' tools\tutor_quality_audit.py
```
