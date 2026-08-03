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

For a controlled one-parameter comparison, the curve interpreter additionally builds
validated mechanism chains. Each chain keeps the parameter change, physical process
steps, expected metric directions, matching observations, conflicting observations,
claim level and Evidence references separate. The deterministic renderer promotes only
consistent chains into public prose, following
`observation → physical mechanism → metric consequence → performance trade-off`.
Multi-parameter comparisons stay descriptive because their individual contributions
cannot be isolated from the current comparison.

## Interactive I-V tutor

The I-V `AI 질문` tab and automatic explanation use the application's dedicated
external-LLM connection. On the first question,
Python freezes the visible Curve selection, device settings, Payload and deterministic
automatic explanation into an analysis snapshot. Later plot selection changes do not
silently alter that conversation; the UI marks the view as changed until the user starts
a new chat.

Each turn uses two bounded stages:

`question → intent JSON → Python validation/routing → metric-specific Context Pack → answer JSON → grounding validation`

The Context Pack includes only relevant metric facts, extraction definitions, validated
mechanism chains, theory, overall assessment, trade-offs and warnings. Questions that do
not use the current result receive no current Curve facts. Public prose cannot contain
Evidence IDs, and current-result answers must return at least one valid Evidence reference
in the separate JSON field. A failed second stage preserves the successful intent so an
identical retry calls only answer generation. HTTP 413/429 diagnostics and the recommended
wait are shown instead of a local substitute answer.

## Field interpretation

Field comparison never uses raw node indices or rendered pixels. Physical gate/interface
landmarks define named regions and normalized coordinates (`channel_u`, interface offset,
oxide depth and bulk depth). Common features include robust regional statistics, a
12-bin normalized channel profile, and region-local top-5% magnitude clusters. Potential,
Electric field, carrier density, current density, SRH and Energy band each have a closed
set of allowed physical conclusions. Field-only results cannot assign parameter causality.

Each supported conclusion also creates an explicit cross-domain verification link:

`spatial observation → physical meaning → I-V metrics to check`

The link is always marked `requires_iv_verification`; it never promotes a Field pattern
into a measured or predicted DIBL, Vth, Ioff, Ion or SS change. The automatic explanation
therefore tells the learner which I-V quantities would confirm or contradict the spatial
interpretation while retaining the Field-only limitation.

## Interactive Field Map tutor

The Field Map `AI 질문` tab uses the same dedicated external provider and two-stage
intent/answer boundary as the I-V tutor, but receives a Field-specific compact Context
Pack. It contains named-region observations, supported physical interpretations,
cross-domain I-V verification links, relevant theory and explicit claim limits. Raw
pixels, mesh indices and internal spatial statistics are not sent as learner-facing
evidence.

The first question freezes the selected generated maps, display, scale, range and device
settings. Later view changes are shown in the status line but do not rewrite the active
conversation. Validation rejects leaked Evidence IDs, invented numbers, Field-only claims
that an electrical metric changed, and claims that Electric field alone proves breakdown.
HTTP failures are shown with the actual stage and retry information; an answer-stage retry
reuses the validated intent checkpoint.

When matching I-V results already exist for every selected Field subject, the snapshot also
builds a cross-domain audit. Subject labels and normalized device parameters must align
exactly; otherwise no I-V fact is admitted. A successful audit adds only the linked,
validated I-V metric observations to the Field question Context Pack. The answer may then
say, for example, that the Field pattern is spatially observed while DIBL increased in the
separate I-V result. It still cannot claim that the Field pattern caused the DIBL change.
The validator checks the reported metric direction and requires the corresponding I-V
Evidence reference. The Field chat status displays `I-V 근거 연동` when this context is
available.

## Mock-first LLM boundary

The automatic external-LLM path uses the `polish-v4` contract. Before the request, Python
replaces analysis numbers in the validated Mock draft with opaque placeholders such as
`__NUM_A__`. The restoration map remains local and is never included in the provider
prompt. The model receives only these masked content blocks and compact constraints—not
the full analysis Payload or preservation manifest. Its task is
`language_polish_only`, and it joins each non-empty section into one paragraph without
sentence-level bullets.

The local validator requires the same sections, one paragraph per non-empty section,
the exact placeholder multiset in the original section, and protected
device/metric/region/direction terms. It restores the original numbers only after those
checks and then runs the existing numeric and causal validation. Numeric-placeholder
failures do not spend a second provider call; repair remains available only for selected
prose/structure failures. In the production GUI, a provider or validation failure is
shown as a Groq error and is not replaced by the Mock draft. The service retains
configurable fallback behavior for tests and non-GUI callers that explicitly enable it.

The GUI has no Mock/LLM selector: learner-facing automatic explanations always use the
dedicated Groq provider, while Python/Mock remains the hidden deterministic analysis
authority. Missing keys and HTTP/network/validation failures are displayed in the
explanation area. The `Preview LLM Prompt` action serves a different purpose from the automatic
polish request: Python converts the internal Payload into a next-stage analysis briefing,
removing schema IDs, scores, selection metadata and output-policy internals while retaining
device settings, extracted results, eligible findings, supported conclusions, integrated
interpretation, excluded findings and warnings. The user can paste that briefing into an
external LLM and continue an interactive, evidence-grounded discussion.

## Common public-answer boundary

Case Study, I–V and Field explanations share the internal `GroundedAnswerContract 1.0`
boundary. It separates summary, observations, interpretations, trade-offs, limitations
and Evidence metadata. The existing four-section automatic response remains compatible:
descriptions map to the summary, comparisons to observations, trade-offs and cautions to
their corresponding layers. Domain-specific interpreters can fill the explicit
interpretation layer in later versions without changing the current GUI response shape.

Evidence IDs remain available internally for validation, persistence and audits. They are
not learner-facing prose: both provider-response validation and Case follow-up validation
reject leaked references such as `evidence_id`, `ev_...`, `metric:...` or
`experiment:conditions`. The Case UI renders human-readable labels such as “DIBL 관찰” or
“실험 조건” while retaining the original reference in the saved session.

## Versions and reproducibility

- Analysis Payload schema: `3.0`
- Grounded answer contract: `1.0`
- Interpretation contract: `1.0`
- Field geometry/features/conclusions: `1.0`
- Deterministic Mock: `deterministic-interpretation-v12`
- Language polish contract: `polish-v4`
- Frozen initial comparison: `tests/baselines/phase1_explanation_baseline.json`
- Final audit: `docs/final_phase8_audit_report.md`

The dependency-free suite is run with the project Conda Python:

```powershell
python tests\run_all.py
```
