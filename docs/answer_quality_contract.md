# Answer quality contract

The Case Study, I-V chat, and Field Map chat pipelines share
`backend.answer_quality`. Domain validators remain responsible for scientific
grounding, numeric checks, extraction definitions, and Field/I-V claim
boundaries. The common contract evaluates learner-facing answer behavior.

## Hard gates

Hard gates reject and repair a provider response when it:

- is empty;
- repeats the same sentence;
- merely echoes the question;
- exposes an internal evidence identifier;
- uses or omits current-result evidence contrary to its route;
- treats a hypothetical or new experiment as an existing result; or
- repeats the user question as its suggested follow-up.

These failures use stable `answer_quality_*` validation codes.

## Soft quality checks

Requested concept coverage, causal depth, and detail depth are reported as
quality warnings rather than provider failures. This keeps natural Korean
paraphrases and concise definition answers from being rejected solely for
style. Korean and English aliases for common device terms are normalized by
the shared evaluator.

## Regression corpus

`tests/fixtures/answer_quality_scenarios.json` contains 36 balanced scenarios:
12 Case, 12 I-V, and 12 Field questions. It covers current results, definitions,
causal explanations, adjacent theory, claim review, hypothetical conditions,
new experiments, cross-domain checks, and out-of-scope questions.

The corpus stores a reference answer and routing expectations. Automated tests
verify corpus balance, uniqueness, hard-gate compliance, and a minimum quality
score. Pipeline tests separately prove that all three online validators return
the same stable code for a shared defect.

## Failure records

Repeated validation failures include a `ValidationFailureRecord`. The default
record stores a question fingerprint, lengths, response shape, model, request
size, stage, and validation codes without storing the raw question or answer.
An explicit `include_replay_content=True` option can create a local replay
fixture when the user intentionally chooses to retain its content.
