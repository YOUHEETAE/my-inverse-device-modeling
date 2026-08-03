# 모델 개발 및 최종 선정 기록

이 문서는 curve model과 fixed-bias field-map model에서 어떤 선택을 했고,
어떤 근거로 최종 모델을 확정했는지를 기록한다. 수치는 저장된 최종 report와
패키지에서 직접 가져왔으며, test는 모델 선정에 사용하지 않았다.

## 1. 핵심 근거 파일

- Curve 최종 선택: `ai/model_artifacts/curve_model/final/pca_xgboost/selection_report.md`
- Curve 최종 test: `ai/model_artifacts/curve_model/final/pca_xgboost/final_test_report.md`
- Curve 전처리: `ai/model_artifacts/curve_model/final/pca_xgboost/preprocessing_config.json`
- Curve manifest: `ai/model_artifacts/curve_model/final/pca_xgboost/final_model_manifest.json`
- Curve final test marker: `ai/model_artifacts/curve_model/final/pca_xgboost/FINAL_TEST_COMPLETE.json`
- Field-map 최종 선택: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/selection_report.md`
- Field-map 최종 test: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.md`
- Field-map 전처리: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/preprocessing_config.json`
- Field-map manifest: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_model_manifest.json`
- Field-map final test marker: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/FINAL_TEST_COMPLETED.json`

## 2. 공통 평가 원칙

- 동일한 device-level split을 두 모델 모두 재사용했다.
- train 1,802 / validation 386 / test 386 기기 분할을 사용했다.
- 선택 과정에서는 validation만 사용했으며, 최종 test는 잠근 모델을 한 번만
  평가하는 용도로 사용했다.
- 선택 기준은 모델 구조, 전처리, validation score, electrical parameter 성공
  여부를 종합한 것이다.
- 중간 restricted-domain 실험은 coverage를 줄여 수치를 개선하는 효과인
  것으로 판단되어 최종 기록에서 제외했다.

## 3. Curve model 요약

### 3.1 최종 모델 및 평가 흐름

- 최종 모델: `PCA + XGBoost`
- 최종 seed: 42
- 최종 selection 상태: full domain, fixed preprocessing, seed-42 모델 잠금
- 후보 모델: PCA + XGBoost / Shared encoder / Residual MLP
- 최종 test는 모델 잠금 후 재학습 없이 386 test device에서 한 번만 수행.
- 제한된 coverage 모델(v1/v2, restricted-domain)은 정확도 면에서 개선이 있었으나
  전체 coverage가 감소하므로 최종 선택에서는 제외됐다.

### 3.1.1 selection context

- `5. Curve Model 보고서.pdf`에 기록된 최종 selection 흐름은 validation-only 기준이다.
- test metrics는 `test_metrics_used=false`로 명시되어 있으며, 최종 test는 별도 한 번의
  평가로만 사용됐다.
- 따라서 최종 신뢰 기준은 validation selection report와 잠금된 final test report,
  그리고 preprocessing contract가 함께 이어지는 상태이다.

### 3.2 최종 transformer / preprocessing

- 최종 transformer config: `selected_legacy_transformer_v1`
- IdVg: `signed_log`, scale `1e-10 mA/um`
- IdVd: `bias_separated`
  - Vg=1.5: `signed_log`, scale `1e-3 mA/um`
  - Vg=3.0: `asinh`, scale `1e-3 mA/um`
- 모든 target은 voltage coordinate별 scaler를 적용했다.
- IdVg target은 TCAD noise floor `1e-10 mA/um` 미만을 floor로 제한했다.
- IdVd 경계 `Vd=0`는 정확히 0으로 처리했다.
- Transformer 내부 `noise_floor`는 0이며, 별도의 추가 clipping은 없다.

### 3.2.1 평가 기준

- 최종 validation ranking은 raw RMSE가 아니라 tail-focused composite score로 결정됐다.
- IdVg score = P95 decade MAE + 0.1 × P95 NRMSE
- IdVd score = P95 NRMSE + 0.25 × P95 decade MAE
- Combined score = (IdVd score + IdVg score) / 2
- 이 평가지표는 `ai/model_artifacts/curve_model/final/pca_xgboost/selection_report.md`,
  `ai/model_artifacts/curve_model/final/pca_xgboost/final_test_summary.json`, 그리고
  `5. Curve Model 보고서.pdf`에 명시돼 있다.
- 실제 RMSE/MAE 평가는 `Linear RMSE`, `P95 NRMSE`, `P95 decade MAE`로 분해돼 기록되며,
  최종 artifact는 이들 지표와 함께 electrical extraction 성공을 복합적으로 평가했다.
- 최종 scaler 선택은 per-coordinate standardization으로, global 대비 통합 tail score가
  15.9% 더 낮았다.

### 3.2.2 선택 근거 요약

- `PCA + XGBoost`는 최소 combined score를 기록했고, validation에서 `386/386` 전기
  파라미터 성공을 유지했다.
- `Shared encoder`는 동일 preprocessing 하에서 validation composite score가
  더 높았고, 전기 파라미터 성공률이 낮아 물리적 일관성이 부족했다.
- `Residual MLP`는 일부 IdVg 성능에서 강점을 보였지만 최종 combined score와
  overall ranking에서 PCA+XGBoost에 뒤처졌다.

### 3.3 validation selection 결과

- 아래 표는 validation selection composite score를 요약한 것이다. 실제 RMSE/MAE 분해는 selection report에 있다.

| 순위 | 모델 | Combined score | IdVd score | IdVg score | 전기 파라미터 성공 |
|---:|---|---:|---:|---:|---:|
| 1 | PCA + XGBoost | 0.037441 | 0.021639 | 0.053243 | 386/386 |
| 2 | Shared encoder | 0.061622 | 0.049889 | 0.073356 | 199/386 |
| 3 | Residual MLP | 0.070224 | 0.069107 | 0.071341 | 127/386 |

### 3.3.1 validation RMSE/MAE 요약

| Curve | Linear RMSE | P95 NRMSE | P95 decade MAE | Max decade MAE |
|---|---|---|---|---|
| IdVd | 0.090751 | 0.018444 | 0.010469 | 1.533341 |
| IdVg | 0.065749 | 0.015453 | 0.048801 | 0.731131 |

- `PCA + XGBoost` validation 지표는 final test report의 locked validation 값을 사용했다.
- baseline 대비 개선: IdVd Linear RMSE -3.16%, IdVg Linear RMSE -7.82%.
- 이 표는 curve 모델의 평균/tail/최대 오류를 명시하여 field-map 요약과 동일한 형태로 비교 가능하게 한다.

### 3.4 최종 test 결과 요약

- 테스트는 잠금된 seed-42 모델을 재학습 없이 한 번만 평가했다.
- `386/386` 전기 파라미터 추출 성공이 validation과 final test 모두 유지됐다.

| Curve | Split | Linear RMSE | P95 NRMSE | P95 decade MAE | Max decade MAE |
|---|---|---|---|---|---|
| IdVd | Locked validation | 0.090751 | 0.018444 | 0.010469 | 1.533341 |
| IdVd | Final test | 0.098402 | 0.020784 | 0.012217 | 2.350210 |
| IdVg | Locked validation | 0.065749 | 0.015453 | 0.048801 | 0.731131 |
| IdVg | Final test | 0.063695 | 0.016317 | 0.070627 | 0.625528 |

- Final test에서 IdVd와 IdVg 모두 tail error가 증가했지만, IdVg linear RMSE는 소폭 개선됐다.
- 이러한 표 형식은 field-map test 요약과 같은 신뢰 수준의 수치 전달을 목표로 한다.

### 3.5 transformer history 정리

- 테스트는 잠금된 seed-42 모델을 재학습 없이 단 한 번 평가했다.
- `386/386` 전기 파라미터 추출 성공이 유지되었고, final test는 validation에서 선택된
  모델의 generalization을 검증했다.

| 지표 | Locked validation | Final test | 변화 |
|---|---:|---:|---:|
| Combined score | 0.035704 | 0.048049 | +34.57% |
| IdVd score | 0.021062 | 0.023838 | +13.18% |
| IdVg score | 0.050346 | 0.072259 | +43.52% |
| 전기 파라미터 추출 | 386/386 | 386/386 | 유지 |

- IdVd에서는 P95 NRMSE와 P95 decade MAE가 test에서 상승했으며, IdVg에서는 linear RMSE가 소폭 감소했지만 tail MAE는 증가했다.
- 이러한 변화는 최종 test가 unseen device와 curve 변동을 포함하는 held-out evaluation임을 보여준다.

### 3.5 transformer history 정리

- `IdVg floor-aware log1p → signed-log`는 중간 후보 항목으로 남은 메모이며,
  최종 state는 `signed_log`로 고정됐다.
- `IdVd asinh → signed-log`는 최종 상태가 아니며,
  실제 최종 IdVd는 `Vg=1.5`에 `signed_log`, `Vg=3.0`에 `asinh`이다.
- 이 두 메모는 중간 candidate 평가 내역으로서 history에 포함되어 있지만,
  최종 평가는 `selected_legacy_transformer_v1` 상태로 수행됐다.
- 따라서 history에는 후보 전환 이력이 함께 기록되어 있으나,
  최종 지표는 최종 report를 기준으로 신뢰할 수 있다.
- `5. Curve Model 보고서.pdf`는 최종 preprocessing과 validation ranking 설계를
  설명하는 progress report이다. 이 PDF는 최종 transform/score 공식과 validation-only
  selection 규칙을 기록하며, 실제 최종 winner는 현재 artifact의 `pca_xgboost`
  패키지가 신뢰할 수 있는 기준이다.

## 4. Field-map model 요약

### 4.1 최종 모델 및 평가 범위

- 최종 모델: fixed-bias coordinate MLP surrogate
- 지원 동작점: `Vg=3 V`, `Vd=3 V`
- validation 386 / test 386 device
- node 모델: baseline coordinate MLP
- element 모델: `element_bulk_physics`

### 4.2 validation selection 결과

| Field | Baseline | Bulk-focused | Bulk + physics | Physics vs baseline |
|---|---|---|---|---|
| ElectricField_x | 0.651389 | 0.437035 | 0.439065 | 32.60% |
| ElectricField_y | 0.348235 | 0.264777 | 0.273125 | 21.57% |
| ElectronCurrent_x | 0.154326 | 0.132678 | 0.141722 | 8.17% |
| ElectronCurrent_y | 1.01117 | 0.682837 | 0.68452 | 32.30% |
| HoleCurrent_x | 0.594806 | 0.526779 | 0.529193 | 11.03% |
| HoleCurrent_y | 0.650954 | 0.41618 | 0.418929 | 35.64% |

### 4.3 physics selection 근거

- Baseline E-direction cosine: 0.750503
- Bulk-focused: 0.716672
- Bulk + physics: 0.873995
- Raw TCAD gradient/field RMS ratio: 4.7604
- Model E vs -grad(V) cosine: 0.873748

### 4.4 최종 test 결과 요약

- test device: 386
- 모델 고정 후 재학습 없음

| Field | Mean RMSE | P50 | P90 | P95 | Max |
|---|---|---|---|---|---|
| Potential | 0.0336571 | 0.0314271 | 0.0469851 | 0.0529573 | 0.0632589 |
| Electrons | 0.0309146 | 0.0299893 | 0.0390939 | 0.0447874 | 0.058553 |
| Holes | 0.0402889 | 0.0386835 | 0.0487383 | 0.0566045 | 0.081787 |
| USRH | 0.0524256 | 0.0516781 | 0.0614174 | 0.0653128 | 0.0801806 |
| ElectricField_x | 0.440756 | 0.434279 | 0.512602 | 0.532764 | 0.583517 |
| ElectricField_y | 0.273718 | 0.282720 | 0.351147 | 0.374755 | 0.439823 |
| ElectronCurrent_x | 0.142019 | 0.139406 | 0.160821 | 0.166395 | 0.179027 |
| ElectronCurrent_y | 0.682906 | 0.712928 | 0.784261 | 0.798805 | 0.846041 |
| HoleCurrent_x | 0.528935 | 0.510742 | 0.615550 | 0.676914 | 0.903488 |
| HoleCurrent_y | 0.417880 | 0.435516 | 0.508690 | 0.531317 | 0.605611 |

### 4.5 한계 및 주의

- fixed-bias 한 점만 지원하므로 동작점 확장은 별도 실험 필요
- `ElectronCurrent_y`, `HoleCurrent_x`, `HoleCurrent_y`에서 tail error가 높음
- domain 외 extrapolation은 주의해야 함

### 4.6 최종 근거 파일

- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/selection_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/preprocessing_config.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_model_manifest.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/FINAL_TEST_COMPLETED.json`

## 5. 현재 확인된 최종 증거

현재 저장소에는 다음 최종 증거 파일이 모두 존재한다.

- `ai/model_artifacts/curve_model/final/pca_xgboost/`
  - `selection_report.md`
  - `final_test_report.md`
  - `final_test_summary.json`
  - `preprocessing_config.json`
  - `final_model_manifest.json`
  - `FINAL_TEST_COMPLETE.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/`
  - `selection_report.md`
  - `final_test_report.md`
  - `preprocessing_config.json`
  - `final_model_manifest.json`
  - `FINAL_TEST_COMPLETED.json`
- `ai/5. Curve Model 보고서.pdf`

이 의미는 다음과 같다.

- 최종 curve model과 field-map model 증거가 모두 남아 있으므로, 현재는
  재실행이 아니라 문서화·검증 단계이다.
- 최종 history는 final package report와 preprocessing config를 근거로 삼으면
  신뢰할 수 있다.
- 재실행이 필요한 경우는 위 파일 중 하나라도 없거나, 최종 transform/selection
  근거가 불명확할 때이다.

## 6. 결론

- curve model: `PCA + XGBoost` (seed 42, full domain, validation에서 최종 선택)
- field-map model: node baseline + `element_bulk_physics` (field RMSE와 물리적 일관성 기준 선택)
- test는 잠금 모델로 한 번만 수행됐으며 재학습 없이 평가됐다.
- 중간 transformer 후보 이력은 history에 포함됐지만, 최종 transformer는
  `selected_legacy_transformer_v1`로 고정됐다.
- 현재 상태에서는 재실행이 필요 없으며, 이 문서와 증거 파일이 history를
  신뢰할 수 있게 만든다.

세부 원본 수치는 각 final package의 `selection_report.json`,
`final_test_report.json`, `metrics.json`, `preprocessing_config.json`을 기준으로 한다.
