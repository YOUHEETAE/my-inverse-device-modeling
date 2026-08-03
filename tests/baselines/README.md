# Explanation baseline fixtures

`phase1_explanation_baseline.json` freezes real-model Payload v3 and deterministic
Mock responses before the eight-phase explanation redesign. It is intentionally
regenerated only when the comparison baseline is being reset.

Regenerate with the project's Conda interpreter:

```powershell
conda activate inverse-device-modeling
python tests/baselines/generate_phase1_baseline.py
```

The fixture covers the default single curve, reinforcing and competing L/T
changes, simultaneous doping changes, three variants, Potential, and Electric
field. Later phases should compare new output with this frozen file rather than
overwrite it.
