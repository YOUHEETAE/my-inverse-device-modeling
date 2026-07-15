# Curve model

Initial problem definitions:

```text
IdVd: [L, T, log10(B), log10(SD), log10(LDD), fixed Vg] -> 101 Id values
IdVg: [L, T, log10(B), log10(SD), log10(LDD), fixed Vd] -> 135 Id values
```

IdVd and IdVg share a stratified device-level split but use separate weights because
their grids, dynamic ranges, and useful target transformations differ. The split
balances individual device features, structure pairs, and doping combinations.

## Final model

The curve-model study is complete. PCA + XGBoost was selected after comparing
three model families, optimized on validation, confirmed across seeds 42-44,
and evaluated once on test without retraining. The production package is:

```text
ai/model_artifacts/curve_model/final/pca_xgboost/
```

Its `README.md` identifies the inference files, and
`final_model_manifest.json` records model hashes, fixed preprocessing, selected
PCA components, and final validation/test status. Intermediate model weights and
search trials were removed after finalization. The prepared dataset is retained
for reproducibility.

The final model covers the full prepared design domain. Earlier restricted-domain experiments improved
metrics by reducing coverage rather than improving the model and are retained
only as a historical note in `docs/archive/domain_restriction_experiment.md`.

## Prepare the dataset

Run from the repository root:

```powershell
python ai/curve_model/data/prepare_dataset.py
```

Generated files are written to `ai/model_artifacts/curve_model/dataset/` and are
excluded from Git.

Generate IdVd and IdVg curves from editable structure and doping parameters with:

```powershell
python ai/curve_model/tools/visualization_curve_model.py
```

If `IDM_DATASET_DIR` is set (for example, `D:\IDM\dataset`), it is used as the
raw input automatically. Generated arrays remain in the repository-local output.
