# Result interpreter

This package consumes structured numerical results rather than replacing the
numerical models.

Current flow:

1. Curve/field analyzers build the common schema-version 3 envelope (`subjects`,
   `comparisons`, `evidence`, `conclusions`, structured `warnings`, and
   `output_policy`).
2. Prompt templates constrain the LLM to the supplied values.
3. `ExplanationService` validates and caches provider responses.
4. The integrated GUI invokes the service in a background thread.
5. `MockExplanationProvider` keeps the complete flow runnable without a network.

Analyzer outputs are normalized by `evidence.py`. Each Evidence record contains
one observation, deterministic IDs, magnitude/confidence/assessment metadata,
suppression reasons, and an explicit numeric-display policy. Suppressed records
remain in the payload for debugging and traceability.

`physical_principles.py` stores parameter/direction-specific principle metadata.
`relationships.py` matches Evidence to those expectations, separates declared
and effective claim levels, and creates physical relationship, conflict,
cross-validation, multi-parameter, or no-meaningful-difference conclusions.

Before rendering, `selection.py` recalculates Evidence importance from metric/field
relevance, magnitude, confidence, comparison role, claim quality, uniqueness, and
linked warnings. It then selects bounded representatives per physical group and
builds only taxonomy-backed trade-off, mixed-group, and baseline-to-variant
conclusions. Renderers consume these decisions and never infer trade-offs.

`safety.py` and `warnings.py` centralize strict numeric sanitization, structured
warnings, caution priority, provider-response validation, and local fallback
responses. Provider and cache failures are isolated from the GUI; invalid values
become JSON `null` and their Evidence is suppressed instead of being replaced by
fabricated zeroes.

The final provider layer supports `mock`, `external_llm`, and `auto` modes.
`ExternalLLMProvider` uses an OpenAI-compatible Chat Completions endpoint configured
only through `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL`. The prompt has an
explicit payload boundary, while `build_llm_render_payload()` sends only selected
or conclusion-referenced Evidence. Prompt/schema/renderer versions participate in
cache keys so policy changes cannot reuse stale prose.

I–V Mock explanations are rendered by `iv_renderer.py` using the catalog in
`iv_templates.py`. The renderer consumes only payload decisions, applies
numeric-display and output policies, validates the four-array response schema,
and returns a safe fallback when analysis data is incomplete.

Field Mock explanations use `field_renderer.py` and `field_templates.py`.
The common renderer validates Field context, restricts comparisons to supplied
spatial Evidence, blocks non-shared-scale visual claims, hides internal Field
statistics, and reuses the I–V response validator and output-policy enforcement.

Display-specific behavior is registered in `field_policies.py`, with templates
in `field_specific_templates.py`. Policies provide Evidence and region ranking,
allowed physical implications, and a category strategy while the common Field
renderer continues to own validation, condition rendering, safety, and limits.

`ai/result_interpreter/providers/groq.py` is the intentionally unfinished external API
boundary. Replacing its `generate()` method and selecting that provider is the
only provider-specific work required later.
