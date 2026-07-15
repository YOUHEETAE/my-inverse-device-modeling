# Residual multi-output MLP (priority 2)

This PyTorch model maps the six normalized device/bias features directly to all
points of one transformed curve. IdVd and IdVg use separate instances and output
sizes. IdVd additionally uses separate `Vg=1.5 V` and `Vg=3.0 V` submodels so
each current regime can use the same target transform as the PCA baseline.

The loss combines transformed point MSE and adjacent-point derivative MSE. AdamW,
gradient clipping, validation early stopping, and restoration of the best epoch
are enabled. The saved `model.pt` contains weights, input normalization, target
inverse transforms, and training history; inference returns raw current in
`mA/um`.

```powershell
python ai/curve_model/training/train_residual_mlp.py --kind both
python -m ai.curve_model.tools.analysis.evaluate_model `
  --model-dir ai/model_artifacts/curve_model/residual_mlp
python ai/curve_model/tools/visualization_evaluation.py `
  --model-preset residual
```

The first full-domain baseline uses width 256, three residual blocks, dropout
0.05, and derivative weight 0.1. It is an architecture baseline, not the selected
production model: PCA + XGBoost remains more accurate on the current dataset,
and the MLP still produces small subthreshold ripples that reduce electrical-
parameter extraction success.
