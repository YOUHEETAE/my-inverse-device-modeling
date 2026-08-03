# System release-readiness report

Date: 2026-08-03  
Scope: application completeness and deployment handoff; infrastructure
deployment itself is excluded.

## Decision

**Technical handoff ready, with external release conditions.**

The application source, model packages, deterministic analyzers, learning
workflows, local session behavior, public error presentation, and documented
runtime contract passed the required local checks. A deployment owner can use
this source state for packaging after it is assigned an exact commit and release
tag.

This is not an unconditional public-deployment approval. The deployment owner
must still supply access control, per-user isolation, secret injection, TLS or
remote-session security, logging policy, and provider budget controls. One live
provider acceptance pass is also required in the target environment.

## Stage results

### 1. User-visible and internal information boundary

Passed.

- Public explanation text no longer includes provider source metadata, token
  usage, prompt previews, model names, request IDs, raw errors, or stack traces.
- Learners receive a generic error category, safe action, retry delay when
  applicable, and session-preservation state.
- Operator diagnostics remain available in process logging and transient
  response objects.
- The boundary is centralized in `backend/public_presentation.py` and covered
  by regression tests.

### 2. Core functional integrity

Passed.

- Both Case Study topics are reachable and preserve their controlled parameter
  changes.
- I-V, Field Map, automatic explanation, free questions, learning feedback,
  session round-trip, deletion, portfolio progress, and multi-condition context
  budgets passed their automated contracts.
- Final curve and field model assets are present and their hashes match.

### 3. Security, privacy, and operational safety

Passed for the repository boundary.

- No tracked secret file was found; `.env.example` contains placeholders only.
- The inspected Git filename history contained no `.env`, credential, secret,
  or API-key filename.
- Local sessions, readiness output, `.env` files, and OMX state are ignored.
- Persisted diagnostics retain only the fields required for safe retry behavior.
- Session filenames are validated, writes are atomic, and deletion removes the
  selected session and its temporary/backup variants.
- Remote multi-user controls are explicitly assigned to the deployment layer in
  `docs/security_privacy_handoff.md`.

### 4. Deployment handoff

Passed.

- Python 3.11 and the Conda environment are pinned.
- Required and optional environment variables are documented.
- Runtime models, writable private paths, entry point, and smoke commands are
  recorded in `deployment/runtime_manifest.json`.
- Developer-specific absolute paths were removed from public setup documents.
- `tools/deployment_readiness.py` gives a machine-readable pass/fail result.

### 5. Final verification evidence

Passed:

- Pytest: **344 passed**
- Canonical test runner: **301 passed, 0 failed, 0 skipped**
- Python compile check: passed
- Git whitespace/error check: passed
- Runtime package hashes: passed for all six final curve/field artifacts
- Model/mesh smoke: finite curves; 2,958 nodes and 5,319 elements; finite field
- UI smoke: all reported GUI contracts passed
- SCE Case smoke: 700 nm to 300 nm, complete; all eight question routes passed
- Oxide Case smoke: 20 nm to 10 nm, expected metric directions present
- Platform audit: 9 of 9 required checks passed; live provider check skipped
- Deployment readiness: all required checks passed

The GUI checks were run through the activated `devsim_env` Conda context. A
direct executable invocation without Conda activation did not initialize Tcl,
which confirms that the documented environment activation step is required.

## Conditions before external feedback

The following are not defects in the application source, but remain mandatory
handoff gates:

1. Commit the approved working tree and create an annotated release tag. The
   current source state is not yet identified by a release commit.
2. Recreate the environment from `environment.yml` in a clean checkout and
   repeat `tools/deployment_readiness.py`, model-package validation, and both
   smoke tests.
3. In the target environment, perform one paid-provider explanation and one
   follow-up question in I-V, Field Map, and Case Study. Confirm success,
   rate-limit handling, and credential isolation.
4. Configure authentication, user/session isolation, secrets, logs, backups,
   deletion, and transport security in the deployment layer.
5. Perform the planned semiconductor-domain expert review before treating the
   generated explanations as qualified instructional content.

## Handoff references

- Runtime and operator instructions: `docs/deployment_handoff.md`
- Security and privacy boundary: `docs/security_privacy_handoff.md`
- User/internal presentation boundary: `docs/user_information_boundary.md`
- Model package details: `ai/DEPLOYMENT.md`
- Runtime manifest: `deployment/runtime_manifest.json`
