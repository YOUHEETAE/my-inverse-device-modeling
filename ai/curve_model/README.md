# Curve model

Initial problem definitions:

```text
IdVd: [L, T, log10(B), log10(SD), log10(LDD), fixed Vg] -> 101 Id values
IdVg: [L, T, log10(B), log10(SD), log10(LDD), fixed Vd] -> 135 Id values
```

IdVd and IdVg share a device split but initially use separate weights because their
grids, dynamic ranges, and useful target transformations differ.

## Roadmap

1. Build a device-level train/validation/test split.
2. Preserve raw currents and compare target transformations.
3. Train PCA regression and direct multi-output MLP baselines.
4. Add a 1D decoder only if simpler baselines are insufficient.
5. Evaluate linear/log errors, worst cases, and extracted electrical parameters.
6. Export the selected models behind one inference API for the GUI.

## Prepare the dataset

Run from the repository root:

```powershell
C:\Users\user\anaconda3\python.exe ai/curve_model/data/prepare_dataset.py
```

Generated files are written to `ai/model_artifacts/curve_model/dataset/` and are
excluded from Git.
