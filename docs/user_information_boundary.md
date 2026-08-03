# User and operator information boundary

This document defines which information may appear in the learning UI and which
information must remain in internal state or operator logs. It applies to Case
Study, I-V Curve, Field Map, automatic explanations, and free-form questions.

## Public learner information

- Simulation and prediction results selected by the learner
- Educational explanations, verified observations, limitations, and caveats
- Friendly evidence labels such as `DIBL 관찰`, never machine evidence IDs
- Whether AI help is available
- A plain-language failure category
- Whether retry is useful and the minimum wait when known
- Whether a question, interpretation checkpoint, or session was preserved
- Save, restore, reset, and delete outcomes

## Operator-only diagnostics

These values remain available in response diagnostics, exceptions, test
artifacts, or server-side logs, but are not rendered in the learner UI:

- Provider name and model identifier
- HTTP status, provider error type, and provider error code
- Raw provider error messages and retry attempt messages
- Request byte counts and prompt/completion token usage
- Rate-limit headers, organization IDs, and request IDs
- Validation codes, repair triggers, and pipeline stage identifiers
- Prompts, structured context packs, condition hashes, and record IDs
- Python exception text, stack traces, and local filesystem paths

API keys, authorization headers, and secret environment values must never be
stored in learner sessions or rendered in either public or diagnostic output.

## Presentation rules

1. Provider diagnostics remain structured data; UI code formats only the public
   category, action, retry wait, and preservation state.
2. A provider failure never shows the raw provider message.
3. Authentication failures tell a learner to contact the service operator.
   They do not instruct a public user to configure a server environment.
4. Internal evidence references are converted to stable educational labels.
5. Automatic explanations do not append provider/model/source or token usage.
6. Prompt-preview and provider-comparison controls are not part of the public
   interface.
7. Unexpected frontend exceptions are logged for operators and shown as a
   generic recovery message to learners.

## Implementation boundary

- `backend/public_presentation.py` owns public AI status and failure text.
- Provider and validation diagnostics remain on their existing response and
  exception objects for tests and operator investigation.
- `frontend/visualization/explanation_panel.py` and
  `frontend/visualization/case_study/panel.py` render only public text.
- `backend/answer_contract.py` prevents machine evidence references from
  entering generated learner prose.

## Regression expectation

Public-text tests must use hostile diagnostics containing a provider model,
organization ID, request ID, raw message, request size, and provider code, then
prove that none appears in the rendered string. Separate assertions must prove
that the structured internal diagnostic remains available for support and
debugging.
