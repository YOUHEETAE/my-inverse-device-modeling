# Curve model definitions

PCA + XGBoost is the finalized production architecture. Residual MLP and shared
encoder implementations remain as reusable research code, but their trained
baseline artifacts were removed after final model selection.

Implementation and experiment order:

1. `pca_xgboost/`: scikit-learn PCA followed by one XGBoost regressor per coefficient.
2. `residual_mlp/`: direct PyTorch multi-output residual MLP.
3. `shared_encoder/`: one device encoder with separate IdVd and IdVg curve heads.

PCA/XGBoost and Residual MLP retain independent curve models. The third model
shares a device representation while retaining task-specific outputs and target
transforms. All architectures use `training/target_transforms.py` and optional
JSON preprocessing configs so comparisons can share identical, invertible target
definitions.
