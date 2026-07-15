# Retired curve-model domain restriction experiment

The `restricted_v1` and `worst_derived_v2` experiments removed difficult device
regions after validation-error analysis. Their reported errors improved, but
their supported coverage fell to 97.98% and 82.67%, respectively. This was an
evaluation-domain reduction, not a model-quality improvement, and the aggressive
v2 rules were derived from validation failures.

The experiment was retired before stage-8 model optimization. Active curve-model
work now follows these rules:

- keep every prepared full-domain sample unless it is a confirmed invalid record;
- use the fixed device-level train/validation/test split;
- improve difficult regions through preprocessing, loss, architecture, and
  hyperparameter optimization;
- select models on validation and evaluate the locked winner once on test.

Machine-local historical artifacts under
`ai/model_artifacts/curve_model/{pca_xgboost_restricted,pca_xgboost_worst_v2}`
were not deleted, so the abandoned experiment remains auditable.
