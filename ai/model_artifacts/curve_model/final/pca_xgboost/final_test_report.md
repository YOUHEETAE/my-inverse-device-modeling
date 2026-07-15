# Locked PCA + XGBoost final test

The locked seed-42 model was evaluated without retraining. This is the single final-test evaluation.

## Overall

| Split | Combined score | IdVd score | IdVg score | Electrical success | Electrical P50 |
|---|---:|---:|---:|---:|---:|
| Locked validation | 0.035704 | 0.021062 | 0.050346 | 386/386 | 0.315906 |
| Final test | 0.048049 | 0.023838 | 0.072259 | 386/386 | 0.327006 |
| Test change | +34.57% | +13.18% | +43.52% | +0 | +3.51% |

## IDVD

| Split | Linear MAE | Linear RMSE | P95 NRMSE | P95 decade MAE | Maximum decade MAE |
|---|---:|---:|---:|---:|---:|
| Locked validation | 0.036585 | 0.090751 | 0.018444 | 0.010469 | 1.533341 |
| Final test | 0.037400 | 0.098402 | 0.020784 | 0.012217 | 2.350210 |
| Test change | +2.23% | +8.43% | +12.68% | +16.70% | +53.27% |

## IDVG

| Split | Linear MAE | Linear RMSE | P95 NRMSE | P95 decade MAE | Maximum decade MAE |
|---|---:|---:|---:|---:|---:|
| Locked validation | 0.018536 | 0.065749 | 0.015453 | 0.048801 | 0.731131 |
| Final test | 0.017246 | 0.063695 | 0.016317 | 0.070627 | 0.625528 |
| Test change | -6.96% | -3.13% | +5.59% | +44.72% | -14.44% |

Positive test change means the error was higher on test; negative means lower.
The test reporting score was computed only after model lock and was not used for selection.
