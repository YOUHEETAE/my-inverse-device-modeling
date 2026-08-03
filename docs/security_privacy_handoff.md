# Security and privacy handoff

This document defines the security boundary of the application source package.
It is an operator handoff, not a substitute for the controls of a web or remote
desktop deployment layer.

## Data visible to learners

The learner interface may show:

- device conditions, predicted curves, field maps, and extracted parameters;
- learning prompts, answers, summaries, and actionable retry guidance;
- generic AI availability states and a rounded retry delay;
- saved Case Study session names and learning progress.

The learner interface must not show:

- API keys, authorization headers, provider organization or request IDs;
- provider response bodies, model-internal validation codes, request byte sizes,
  token accounting, prompt payloads, or stack traces;
- developer filesystem paths or raw Python exceptions.

`backend/public_presentation.py` is the shared presentation boundary for AI
source labels, failure messages, and persisted diagnostics.

## Local session storage

Case Study sessions are stored under `runtime/learning_sessions/`. They contain
the learner's questions, educational responses, selected Case state, and
progress. Treat this directory as user data.

- Session identifiers are validated before they are used as filenames.
- Writes use a temporary file and atomic replacement.
- Session deletion removes the selected JSON file and its temporary/backup
  variants.
- Saved diagnostics are reduced to the failure category, pipeline stage, HTTP
  status, retry delay, and whether an intent checkpoint exists.
- Raw provider messages, response bodies, headers, model names, request sizes,
  usage details, and fallback details are not persisted.

The entire `runtime/` state is ignored by Git and must not be included in a
release archive, diagnostic bundle, or public repository.

## Provider credentials and outbound data

The Groq credential is read from the environment variable named by
`LLM_API_KEY_ENV` (default: `GROQ_API_KEY`). A real key must never be placed in
`.env.example`, source code, a session file, screenshots, or support logs.

The application sends selected numerical evidence, conditions, learning
context, and the learner's question to the configured provider. An operator
must disclose this external processing to users and apply an appropriate data
retention policy. Do not enter personal, confidential, or regulated data into
free-question fields.

## Trust boundary for remote deployment

This repository supplies a Tk desktop application; it does not contain an HTTP
server, user accounts, authentication, authorization, TLS termination, CSRF or
CORS policy, or multi-user session isolation. If the application is exposed
through a browser, remote desktop, streaming service, or custom web wrapper,
that deployment layer must provide:

- authenticated access and per-user authorization;
- a separate writable session namespace for each user;
- TLS and secure secret injection;
- request and concurrency limits;
- access-controlled server logs;
- backup, retention, export, and deletion policy;
- process isolation so one learner cannot read another learner's runtime files.

Do not represent those controls as implemented by this repository.

## Release checks

Before handoff:

1. Confirm `.env`, `runtime/*.json`, `runtime/learning_sessions/`, and `.omx/`
   are ignored and absent from the release package.
2. Run `python tools/deployment_readiness.py`.
3. Run the complete verification commands in `docs/deployment_handoff.md`.
4. Rotate any credential that has appeared in a terminal capture, issue, chat,
   or untrusted log.

