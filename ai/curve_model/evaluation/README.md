# Curve evaluation

The finalized curve model is `model_artifacts/curve_model/final/pca_xgboost`.
It covers the complete prepared design domain. Validation selected the model;
the locked model was then evaluated once on test without retraining.

Interactive curve and electrical-parameter inspection defaults to the final
model:

```powershell
python ai/curve_model/tools/visualization_evaluation.py
```

The final evidence is stored with the model:

- `selection_report.md`: baseline-to-optimized validation comparison
- `final_test_report.md`: locked validation-to-test comparison
- `evaluation/validation_report.json`: complete validation metrics
- `evaluation/test_report.json`: complete one-time test metrics
- `FINAL_TEST_COMPLETE.json`: completion and model-integrity record

The report includes linear MAE/RMSE, NRMSE, R-squared, signed-log and decade
errors, distribution percentiles, and re-extracted electrical-parameter errors.
