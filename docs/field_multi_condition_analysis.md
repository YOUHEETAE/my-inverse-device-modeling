# Field multi-condition analysis

Stage 4 added a reusable multi-condition Field analyzer. The desktop GUI now
deliberately limits interactive selection to two maps, following the final
product decision.

## Selection and display

- The desktop GUI accepts one or two checked Field conditions.
- One condition is shown as a single map.
- Two conditions are both shown.
- A third checkbox is immediately reverted and a status message explains that
  the maximum is two.
- The backend still supports three or more conditions for tests, batch audits,
  and possible future tools. In that non-GUI path, the planner selects two
  representative maps:
  - the minimum and maximum condition for a controlled sweep;
  - the first controlled pair for a mixed group when one exists; or
  - the baseline and the largest compound change otherwise.
- Scalar-map color normalization includes every selected condition, including
  intermediate conditions that are not displayed.

The UI therefore labels the selector as `Select up to 2 curves`; it does not
silently analyze hidden intermediate maps.

## Analysis behavior

All pairwise Field evidence is generated for the selected conditions.
The common comparison plan still determines the allowed claim level.

For a controlled sweep, Python orders the conditions by the changed parameter
and builds regional trends from the same named region:

- monotonic increase;
- monotonic decrease;
- stable within the local tolerance; or
- non-monotonic.

Potential, field, carrier, current-density, and SRH trends use the regional
p95 magnitude. Energy-band trends use three explicit cuts:

- Source plateau to the Source-side local Ec maximum for the channel-entry
  barrier;
- Source-edge to Drain-edge Ec slope for the horizontal channel slope; and
- surface to Deep-bulk Ec separation for vertical band bending.

For mixed groups, no global trend is inferred from arbitrary selection order.
Controlled pairs are prioritized and the representative pair is explained
with the existing multi-parameter claim limits.

## Answer boundary

The automatic explanation explicitly states:

- how many conditions were analyzed;
- which two maps are displayed;
- whether the result is a controlled sweep or mixed group;
- the regions or cuts to inspect; and
- that Field trends remain spatial predictions and require I-V verification
  for electrical metrics.

The LLM only polishes this deterministic draft. It cannot change the
comparison plan, promote a mixed group into a controlled comparison, or turn
a Field trend into a verified electrical result.
