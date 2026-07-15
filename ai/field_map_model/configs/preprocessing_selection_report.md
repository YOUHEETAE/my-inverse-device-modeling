# Field-map preprocessing selection

The screening reused the locked curve-model split and loaded zero test cases.
Each run sampled the train and validation devices equally by `bulk`, `oxide`,
and `gate` region. Tiny solver values were retained, while data-driven
resolution floors were used in the common evaluation metric so that candidates
could not win merely by magnifying numerical noise.

## Two-seed validation result

| Domain | Recipe | Seed 42 | Seed 123 | Mean |
|---|---|---:|---:|---:|
| Node | signed-log q10 + standard | 0.026059 | 0.025668 | **0.025864** |
| Node | asinh q10 + standard | 0.026325 | 0.025677 | 0.026001 |
| Element | asinh q10 + standard | 0.440107 | 0.441825 | **0.440966** |
| Element | signed-log q10 + standard | 0.439882 | 0.442280 | 0.441081 |

The selected node recipe therefore uses identity for `Potential`, `log1p` for
the non-negative carrier densities, and signed-`log1p` for `USRH`. The selected
element recipe uses `asinh` for all signed electric-field and current-density
components. Every transformed field receives its own train-fitted standard
scaler.

`NetDoping` remains a known spatial input. It is never predicted as a target.
No raw samples were removed or overwritten during this selection.
