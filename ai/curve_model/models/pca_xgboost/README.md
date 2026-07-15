# PCA + XGBoost (priority 1)

The transformed current curves are compressed with scikit-learn PCA. A
scikit-learn StandardScaler normalizes input features, one XGBoost
regressor predicts each retained coefficient, and the inverse PCA reconstructs
the complete curve. Validation curves control per-component early stopping, and
joblib stores the complete fitted pipeline. This is the first model to train
because the dataset is a small-to-medium tabular regression problem with smooth,
highly correlated outputs.

IdVd uses a bias-separated wrapper around two independent PCA + XGBoost models.
This prevents the near-off `Vg=1.5 V` curves and on-state `Vg=3 V` curves from
sharing one PCA basis and target scale. The saved wrapper still exposes one model
artifact and dispatches inference using the fixed-bias input feature, so the
evaluation GUI does not require separate user controls.
