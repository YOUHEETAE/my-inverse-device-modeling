# Field-map model final test

Test devices: 386. The validation-selected model was frozen before this one-time evaluation.

## Full-map evaluation

| Field | Mean | P50 | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|
| Potential | 0.0336571 | 0.0314271 | 0.0469851 | 0.0529573 | 0.0632589 |
| Electrons | 0.0309146 | 0.0299893 | 0.0390939 | 0.0447874 | 0.058553 |
| Holes | 0.0402889 | 0.0386835 | 0.0487383 | 0.0566045 | 0.081787 |
| USRH | 0.0524256 | 0.0516781 | 0.0614172 | 0.0653128 | 0.0801806 |
| ElectricField_x | 0.440756 | 0.434279 | 0.512602 | 0.532764 | 0.583517 |
| ElectricField_y | 0.273718 | 0.28272 | 0.351147 | 0.374755 | 0.439823 |
| ElectronCurrent_x | 0.142019 | 0.139406 | 0.160821 | 0.166395 | 0.179027 |
| ElectronCurrent_y | 0.682906 | 0.712928 | 0.784261 | 0.798805 | 0.846041 |
| HoleCurrent_x | 0.528935 | 0.510742 | 0.61555 | 0.676914 | 0.903488 |
| HoleCurrent_y | 0.41788 | 0.435516 | 0.50869 | 0.531317 | 0.605611 |

Values are per-device RMSE in each field's frozen evaluation/transform space.

## Input and physics checks

- Analytic NetDoping signed-log RMSE (mean): 0.000121927
- Negative predicted carrier values: 0 maximum per device
- Raw E vs -grad(V): normalized RMSE 4.62038, cosine 0.969107, gradient/field RMS ratio 4.74501
- Model E vs -grad(V): normalized RMSE 3.66416, cosine 0.873748, gradient/field RMS ratio 3.70694
- Model/raw median neighbor-jump ratio: electron current P50 0.790489, hole current P50 0.950443
- Regenerated mesh: 5611 nodes / 10481 triangles; all outputs finite: True

Region metrics and current-neighbor jump distributions are in `final_test_report.json`; device errors are in `test_device_metrics.csv`.
