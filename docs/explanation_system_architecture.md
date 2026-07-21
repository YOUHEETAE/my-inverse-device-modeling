# MOSFET explanation system architecture

## Production flow

The production Analyzer-guided flow is Mock-first:

`Prediction → extraction → Evidence → interpretation → deterministic Mock draft → optional LLM language polish`

Python owns all analysis decisions. The Payload contains performance summaries,
parameter effects and interactions, observed trade-offs, geometry alignment, named
regions, normalized profiles, regional clusters, Field-specific conclusions, quality
gates, warnings and traceable Evidence IDs.

The deterministic Mock converts that completed analysis into four sections:
`descriptions`, `comparisons`, `tradeoffs`, and `cautions`. A missing Mock statement is
therefore a Python renderer defect; an LLM is not expected to recover omitted analysis.

## Curve interpretation

Curve results are organized into off-state control, short-channel control, subthreshold,
drive, threshold, saturation and curve-shape areas. Parameter expectations are compared
with observed Evidence and multi-parameter changes are classified as reinforcing,
competing, independent or uncertain. Descriptive trade-offs remain available even when
individual parameter causality cannot be assigned. A physically ambiguous DIBL sign is
retained as data but excluded from directional performance judgment.

## Field interpretation

Field comparison never uses raw node indices or rendered pixels. Physical gate/interface
landmarks define named regions and normalized coordinates (`channel_u`, interface offset,
oxide depth and bulk depth). Common features include robust regional statistics, a
12-bin normalized channel profile, and region-local top-5% magnitude clusters. Potential,
Electric field, carrier density, current density, SRH and Energy band each have a closed
set of allowed physical conclusions. Field-only results cannot assign parameter causality.

## Mock-first LLM boundary

The automatic external-LLM path uses the `polish-v3` contract. The model receives only the
validated Mock draft plus a preservation manifest—not the full analysis Payload. Its task
is `language_polish_only`, and it joins each non-empty section into one paragraph without
sentence-level bullets.

The local validator requires the same sections, one paragraph per non-empty section, numeric tokens and
protected device/metric/region/direction terms. It forbids new causal claims. One repair
is allowed; a second failure discards the LLM response and returns the exact Mock draft.

The GUI exposes only `mock` and `external_llm`; both use the same completed Python/Mock
analysis. The `Preview LLM Prompt` action serves a different purpose from the automatic
polish request: Python converts the internal Payload into a next-stage analysis briefing,
removing schema IDs, scores, selection metadata and output-policy internals while retaining
device settings, extracted results, eligible findings, supported conclusions, integrated
interpretation, excluded findings and warnings. The user can paste that briefing into an
external LLM and continue an interactive, evidence-grounded discussion.

## Versions and reproducibility

- Analysis Payload schema: `3.0`
- Interpretation contract: `1.0`
- Field geometry/features/conclusions: `1.0`
- Deterministic Mock: `deterministic-interpretation-v8`
- Language polish contract: `polish-v3`
- Frozen initial comparison: `tests/baselines/phase1_explanation_baseline.json`
- Final audit: `docs/final_phase8_audit_report.md`

The dependency-free suite is run with the project Conda Python:

```powershell
C:\Users\T590\anaconda3\envs\devsim_env\python.exe tests\run_all.py
```
