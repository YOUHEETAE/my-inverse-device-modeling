# AI modeling workspace

The main end-user entry point is the integrated final-model GUI:

```powershell
conda activate devsim_env
python ai/integrated_visualization_app.py
```

전체 실험 흐름, 변경한 전처리·모델 변수, validation 선택 근거, 한 번의 final
test 결과와 알려진 한계는 `ai/MODEL_SELECTION_HISTORY.md`에 통합되어 있다.

Install its Python dependencies with `pip install -r ai/requirements.txt` when
setting up a new environment. Tkinter must also be available in the Python
installation. The two large curve weights use Git LFS; run `git lfs install` once
on a new machine. Normal `git clone`, `git pull`, and `git push` then transfer the
weights automatically.

The workspace is divided into these model families:

```text
ai/
  curve_model/         Device parameters and bias -> IdVd / IdVg curves
  field_map_model/     Device parameters and operating point -> spatial fields
  result_interpreter/  LLM-based interpretation of numerical model results
  shared/              Schemas and utilities shared across model families
  tools/               Stable command wrappers
  model_artifacts/     Local experiments plus Git-tracked final packages
```

Raw TCAD data remains under `tcad/data_extraction/dataset`. The AI workspace does
not duplicate those source files; it stores only reproducible processed arrays and
model outputs in `ai/model_artifacts`.

The integrated GUI uses these Git-tracked runtime assets:

```text
ai/model_artifacts/curve_model/final/pca_xgboost/
ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/
tcad/data_extraction/base_case/gmsh_mos2d.geo
```

The curve package contains the final IdVd/IdVg PCA+XGBoost weights. The field-map
package contains node/element coordinate-MLP checkpoints, NumPy runtime weights,
and their fitted scalers and target transforms. The integrated GUI does not import
PyTorch. Raw datasets, baseline checkpoints, candidates, and generated plots are
intentionally ignored; see `ai/model_artifacts/README.md`.

For a stable wrapper command, `python ai/tools/visualization_models.py` launches
the same application.
