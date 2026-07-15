# Stage 8 baseline validation comparison

Lower is better for all error and selection-score columns. Test data was not used.

| Rank | Model | Combined score | IdVd score | IdVg score | IdVd MAE | IdVg MAE | IdVd P95 NRMSE | IdVg P95 NRMSE | IdVd P95 decade MAE | IdVg P95 decade MAE | Electrical success | Electrical P50 score |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | pca_xgboost | 0.037441 | 0.021639 | 0.053243 | 0.0381662 | 0.0199924 | 0.0189728 | 0.0164715 | 0.0106654 | 0.0515955 | 386/386 (100.0%) | 0.363762 |
| 2 | shared_encoder | 0.061622 | 0.049889 | 0.073356 | 0.154305 | 0.0539647 | 0.0436869 | 0.032647 | 0.0248066 | 0.0700908 | 199/386 (51.6%) | 7.67034 |
| 3 | residual_mlp | 0.070224 | 0.069107 | 0.071341 | 0.209945 | 0.0776132 | 0.0594031 | 0.0481591 | 0.0388153 | 0.0665253 | 127/386 (32.9%) | 6.77524 |

Selection score definition:

- IdVd: `P95 NRMSE + 0.25 * P95 decade MAE`
- IdVg: `P95 decade MAE + 0.10 * P95 NRMSE`
- Combined: mean of the IdVd and IdVg scores
