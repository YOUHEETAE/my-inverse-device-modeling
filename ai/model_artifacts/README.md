# Model artifacts policy

The two finalized, deployable packages are tracked by Git:

```text
model_artifacts/
  curve_model/final/pca_xgboost/
  field_map_model/final/coordinate_mlp_physics/
```

Each final package contains the weights and fitted preprocessing state required
for inference, a manifest with hashes, and the retained validation/final-test
reports. Four small curve-baseline reports used as evidence by
`ai/MODEL_SELECTION_HISTORY.md` are also retained: the three family-specific
`validation_report.json` files and `baseline_comparison.md`. All datasets,
baseline checkpoints, optimization candidates, other optimization outputs,
screening outputs, and generated plots remain local and are ignored by Git.

Do not delete ignored datasets when future retraining or audit work is planned;
they are excluded from deployment, not declared disposable.
