# Curve inference

The final predictor exposes one GUI-facing API while loading separate IdVd and
IdVg weights and their preprocessing metadata.

Run the interactive final-model visualization with:

```powershell
python ai/curve_model/tools/visualization_curve_model.py
```

The editable inputs are gate length, oxide thickness, bulk doping,
source/drain doping, and LDD doping. The plots show generated IdVd and IdVg
curves on linear and logarithmic current axes for the fixed biases supported by
the finalized model.

Compare raw TCAD curves against final-model predictions with:

```powershell
python ai/curve_model/tools/visualization_model_check.py
```
