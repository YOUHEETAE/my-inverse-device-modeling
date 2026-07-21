# Integrated model deployment

## Git-tracked runtime

The integrated application is launched with:

```powershell
git lfs install
git lfs pull
conda env create -f environment.yml
conda activate inverse-device-modeling
python ai/tools/check_runtime_package.py
python frontend/app.py
```

Its runtime path is intentionally limited to:

```text
frontend/app.py
frontend/visualization/
backend/explanation/
ai/shared/field_data.py
ai/curve_model/{data,inference,models,training/target_transforms.py}
ai/field_map_model/{inference,models}
ai/model_artifacts/curve_model/final/pca_xgboost/
ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/
tcad/data_extraction/base_case/gmsh_mos2d.geo
tcad/data_extraction/parameter_extraction_core.py
```

The curve pickle contains fitted PCA, XGBoost, feature-scaler, and target-transform
objects. Its associated JSON files freeze the sweep grid and preprocessing state.
The field-map package contains separate node and element checkpoints, NumPy runtime
weights, exported feature scalers, and target transforms. The GUI uses the NumPy
weights so its Matplotlib process does not need PyTorch. All final-package files
should be committed.

Install runtime dependencies in a fresh environment with:

```powershell
pip install -r ai/requirements.txt
```

The two curve-model pickle files use Git LFS. On a new machine, install Git LFS
once before cloning, or run `git lfs install` followed by `git lfs pull` inside
an existing clone. The small field-map checkpoints remain regular Git files.

Then validate the package and run a model/mesh smoke test:

```powershell
python ai/tools/check_runtime_package.py
python frontend/app.py --smoke-test
```

## Local-only artifacts

The following are useful for training or audits but must not be pushed:

```text
ai/model_artifacts/curve_model/dataset/
ai/model_artifacts/curve_model/optimization/  # except the four retained baseline reports
ai/model_artifacts/field_map_model/dataset/
ai/model_artifacts/field_map_model/baselines/
ai/model_artifacts/field_map_model/candidates/
ai/model_artifacts/field_map_model/preprocessing_screening/
ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/examples/
tcad/data_extraction/dataset/
tcad/data_extraction/runs/
```

These paths are ignored rather than deleted so the training history remains
available on the development machine.

## Weight storage

The largest final file is the IdVg model (about 64.5 MiB). Although this is below
GitHub's 100 MiB hard limit, it exceeds GitHub's recommended 50 MiB threshold.
The IdVd and IdVg weights therefore use Git LFS so repeated model updates do not
bloat normal Git history. With Git LFS installed, ordinary `git clone`, `git pull`,
and `git push` transfer the weights automatically; no separate model URL or manual
copy step is required.
