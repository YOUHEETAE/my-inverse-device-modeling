# Stage 7 platform readiness

Stage 7 freezes a reproducible integration gate for the current learning
platform. It checks scientific and application boundaries together instead of
considering a passing GUI launch sufficient.

## Required audit checks

The readiness command verifies:

1. both topic configurations load and change exactly one model parameter;
2. curriculum prerequisites are reachable without a cycle;
3. one session per Case survives JSON save and restore without mixing topics;
4. portfolio recommendations advance from SCE to the Oxide Case;
5. both real models run and preserve their released electrical directions; and
6. local tutor answers use current-result evidence and the expected theory.
7. Comparison Planner distinguishes controlled, compound, and sweep analyses;
8. compound comparisons remain at association-level claims;
9. required runtime model/geometry assets exist; and
10. a real 700/500/300 nm sweep sends adjacent pairs and remains inside the
    I-V/Field context budgets.

Run:

```powershell
python tools\platform_readiness_audit.py
```

Use `--skip-models` for the fast structural subset. The command prints strict
JSON and exits non-zero if a required check fails. `--output PATH` saves the
same report.

## Current released model contracts

| Case | Controlled change | Required directions |
|---|---|---|
| Channel Length/SCE | L: 700 nm → 300 nm | Ion increase, Ioff increase, DIBL increase |
| Oxide/Gate control | T: 20 nm → 10 nm | gm increase, SS decrease, Ioff increase |

Both current analyses report `partial` because the common analyzer does not
promote every optional metric or Field claim. This is not treated as failure:
the required Case metrics and spatial observations must still be present.

## Multi-condition release contract

The model-backed audit creates the 700/500/300 nm L sweep and verifies both
I-V and Electric-field analysis paths. Python must identify
`controlled_sweep`, order the values as 300/500/700 nm, and send only the two
adjacent comparisons to a free-question answer request. Fixed parameters are
factored into one block instead of repeated per Curve.

The serialized context limits are:

- I-V: below 16 KB
- Field: below 18 KB

These are application regression budgets, not Groq account limits. Live token
usage can still vary with the tokenizer and generated output length.

## Environment-level check

The deterministic readiness audit deliberately does not spend Groq quota.
Live Groq availability, model access, TPM limits, and response behavior are
reported as an optional skipped check. The report still records the configured
model, base URL, key environment-variable name, and whether a key is present;
it never prints the key itself. Before distribution on another machine,
send one Case, one I-V, and one Field question with that machine's API key and
confirm provider usage and errors are visible.

## Final GUI check

Run:

```powershell
python frontend\app.py --ui-smoke-test
```

This constructs the hidden GUI, switches between both Cases, opens the
portfolio dialog, verifies session controls and preserved tabs, and exits
non-zero on failure.

## Current validation result

The final Stage 7 run completed with:

- readiness required checks: 9/9 passed;
- optional Groq live check: skipped without spending a call;
- I-V sweep context: 14,946 bytes;
- Field sweep context: 13,473 bytes;
- pytest: 337 passed;
- legacy integration runner: 301 passed, 0 failed;
- runtime model hash/package check: passed;
- model smoke and hidden GUI smoke: passed.

The release-command sequence also exposed and fixed an import-order defect:
loading I-V chat before `backend.learning.readiness` previously created a
cycle. Readiness now imports the heavy chat analyzers only while its
model-backed context check is running, and a fresh-process regression test
protects the GUI import order.
