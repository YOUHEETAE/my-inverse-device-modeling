# Deployment handoff

The repository is packaged as a local Tk learning application. Deployment
infrastructure is intentionally outside this scope. The receiving operator
should preserve the runtime contract below.

## Supported runtime

- Windows or another desktop environment with Tk support
- Python 3.11, as pinned by `environment.yml`
- Git LFS for the two final curve-model pickle files
- A display session for the GUI
- Write access to `runtime/`
- Outbound HTTPS access to the configured AI provider when AI explanations are
  enabled

Create the environment and fetch model assets:

```powershell
git lfs install
git lfs pull
conda env create -f environment.yml
conda activate inverse-device-modeling
```

The checked-out `tcad/devsim` submodule is a development and TCAD workflow
dependency. The packaged inference GUI uses the tracked geometry and extraction
modules listed in `ai/DEPLOYMENT.md`; operators who also run TCAD workflows
should initialize the submodule explicitly.

## Configuration

Required for external AI answers:

```text
GROQ_API_KEY
```

Optional overrides:

```text
LLM_MODEL
LLM_BASE_URL
LLM_API_KEY_ENV
```

Inject secrets through the deployment platform or process environment. The app
does not automatically load `.env` files. Do not place a real key in a release
archive.

## Writable and private state

`runtime/learning_sessions/` is created on demand and contains learner data.
Give it a persistent, private, per-user volume when sessions must survive
restarts. Do not share one directory across untrusted users. Exclude all of
`runtime/` from static assets and support bundles.

## Launch and health-equivalent checks

This is not an HTTP service, so it has no readiness URL. Use these commands:

```powershell
python tools/deployment_readiness.py
python ai/tools/check_runtime_package.py
python frontend/app.py --smoke-test
python frontend/app.py --ui-smoke-test
python frontend/app.py
```

The first four commands must exit with code 0. The final command starts the
interactive application.

## Release qualification

Run in the environment that will be handed to the deployment owner:

```powershell
python -m pytest -q
python tests/run_all.py
python tools/case_study_smoke.py
python tools/oxide_case_smoke.py
python tools/platform_readiness_audit.py
```

The platform audit intentionally treats a live paid-provider call as optional.
Before public feedback, perform one controlled AI explanation and one follow-up
question in each of I-V, Field Map, and Case Study. Confirm that a disconnected
provider produces a generic retry message rather than a mock answer or internal
diagnostics.

## Operator decisions outside this repository

The deployment owner remains responsible for:

- the access mechanism, authentication, TLS, and user isolation;
- secret storage and rotation;
- provider spend, rate limits, quotas, and outbound-data disclosure;
- log collection and redaction;
- backup and deletion policy for learner sessions;
- process supervision and resource limits.

Record the exact Git commit and annotated release tag after the final source
state is approved. Do not deploy an unidentified dirty working tree.

