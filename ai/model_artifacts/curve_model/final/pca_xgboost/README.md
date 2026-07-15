# Final curve model

The end-to-end experiment and selection rationale is summarized in
`ai/MODEL_SELECTION_HISTORY.md`.

This directory is the finalized PCA + XGBoost curve-model package. The seed-42
model was selected on validation and evaluated once on test without retraining.

Inference requires more than the two `model.pkl` files:

- `idvd/model.pkl` and `idvg/model.pkl`: input scaler, PCA, and XGBoost models
- each `target_transform.json`: raw-current inverse transform
- each `inference_metadata.json`: feature order, fixed bias, and voltage grid
- `preprocessing_config.json`: fixed common preprocessing contract
- `domain_policy.json`: supported full design domain

Files under `evaluation/`, `metrics.json`, and the Markdown/JSON reports are not
required for prediction, but are retained as final evidence.
`final_model_manifest.json` records reproducibility and model identity.

Interactive curve generation from structure and doping parameters:

```powershell
python ai/curve_model/tools/visualization_curve_model.py
```

The prepared dataset is retained separately under
`ai/model_artifacts/curve_model/dataset/` for reproducibility. Optimization
trials and alternative model weights are intentionally not part of this package.

The two `model.pkl` files are stored through Git LFS. After cloning, run
`git lfs pull` if the model files are still small LFS pointer files.
