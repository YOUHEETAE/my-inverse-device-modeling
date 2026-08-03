# Comparison focus routing

Stage 5 lets I-V and Field free questions narrow an existing Comparison Plan
without creating a new analysis or increasing its claim level.

## Resolution order

Python resolves comparison focus from the frozen analysis snapshot:

1. Explicit displayed labels such as `Curve 2` and `Curve 3`.
2. Existing changed-parameter values such as `500 nm` and `300 nm`.
3. A request for the full sweep or overall trend.
4. The previous turn's saved focus for phrases such as `그 둘`.
5. The existing Comparison Plan default.

A bare numeric value is not treated as a device target unless the question
also contains a comparison cue. Values are matched only against parameters
that actually vary in the frozen plan.

The resolver returns one of:

- `full_plan`;
- `specific_pair`;
- `subject_group`;
- `single_subject`; or
- `clarification`.

When more than two subjects exist and a comparison request does not identify
its targets, the local router asks which pair to compare before spending an
answer-generation API call.

## Evidence boundary

For a specific pair:

- only that comparison is included in the Context Pack;
- metric, mechanism, spatial, and cross-domain evidence is filtered to that
  pair;
- Field conclusions are re-ranked from the pair's original eligible Evidence
  even when it is not one of the two representative maps; and
- multi-condition sweep trends are omitted because the question no longer
  asks about the full sweep.

The original Comparison Plan remains in the Context Pack together with the
resolved focus. The focus can filter an existing plan but cannot create a new
comparison or promote the original claim level.

For compound comparisons, the response validator rejects direct
single-parameter attribution such as saying that one changed parameter
definitively caused the result. General theory and explicit statements that
the individual contribution cannot be isolated remain allowed.

## Conversation continuity

Each successful GUI turn stores its resolved focus as structured metadata.
A follow-up such as `그 둘 중에서는 SS가 왜 달라?` reuses the prior pair
without asking the LLM to reconstruct it from prose. Starting a new chat still
creates a fresh frozen snapshot and clears this conversational focus.
