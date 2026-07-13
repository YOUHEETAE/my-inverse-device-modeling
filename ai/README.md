# AI modeling workspace

The AI system is divided into clearly separated model families:

```text
ai/
  curve_model/         Device parameters and bias -> IdVd / IdVg curves
  field_map_model/     Device parameters and operating point -> spatial fields
  result_interpreter/  LLM-based interpretation of numerical model results
  shared/              Schemas and utilities shared across model families
  model_artifacts/     Generated datasets, weights, metrics, and plots (not tracked)
```

Raw TCAD data remains under `tcad/data_extraction/dataset`. The AI workspace does
not duplicate those source files; it stores only reproducible processed arrays and
model outputs in `ai/model_artifacts`.

Development starts with `curve_model`. IdVd and IdVg initially use separate model
weights while sharing the same device-level train/validation/test split.
