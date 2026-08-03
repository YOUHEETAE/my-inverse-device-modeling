# Final field-map model

The end-to-end experiment and selection rationale is summarized in
`ai/MODEL_SELECTION_HISTORY.md`.

Fixed-bias (`Vg=3 V`, `Vd=3 V`) coordinate-MLP surrogate. The node model is the validated baseline; the element model uses bulk/channel-focused sampling and an electric-field direction loss.

## Final model summary

- Selected architecture: baseline node coordinate MLP + `element_bulk_physics` element coordinate MLP
- Validation selection: improved element field RMSE and stronger electric-field direction consistency
- Final test: one-time evaluation on 386 test devices after model lock
- Key field-map test results: mean RMSE ranges from 0.0309 (Electrons) to 0.6829 (ElectronCurrent_y) in frozen evaluation space

The package contains both training checkpoints, NumPy runtime weights, fitted feature scalers, fitted target transforms, preprocessing metadata, validation selection, and the one-time final-test report. Runtime inference uses `model.npz`; PyTorch is not required by the visualization application.

```python
from pathlib import Path
from ai.field_map_model.inference import FieldMapPredictor, generate_gmsh_mesh

root = Path('.')
mesh = generate_gmsh_mesh(1000, 10, root / 'tcad/data_extraction/base_case/gmsh_mos2d.geo')
predictor = FieldMapPredictor(root / 'ai/model_artifacts/field_map_model/final/coordinate_mlp_physics')
result = predictor.predict(mesh, 1000, 10, 1e16, 5e20, 1e18)
```

The model is valid for the training design space and the fixed bias only.
