# Curve-model training

The finalized production artifact is
`model_artifacts/curve_model/final/pca_xgboost`. Do not retrain or tune it using
the recorded test result.

Its fixed preprocessing contract is
`configs/preprocessing/selected_legacy.json`:

- IdVd, Vg=1.5 V: signed-log with scale `1e-3 mA/um`
- IdVd, Vg=3.0 V: asinh with scale `1e-3 mA/um`
- IdVg: signed-log with scale `1e-10 mA/um`
- per-coordinate target scaling fitted on training data only

The selected PCA/XGBoost recipe is recorded in
`configs/pca_xgboost_final.json`. It uses seed 42, up to 32 PCA components,
8 selected components for each IdVd bias, 28 for IdVg, up to 8000 trees, and
200-round early stopping. IdVd uses `physical_v1` feature engineering; IdVg
uses the six prepared inputs directly. Tail weighting is disabled and the full
prepared design domain remains in scope.

The prepared dataset remains under `model_artifacts/curve_model/dataset` for
reproducibility. Final model identity, reports, and hashes are stored with the
production artifact; intermediate optimization weights are intentionally
discarded after finalization.
