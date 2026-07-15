# 모델 개발 및 최종 선정 기록

이 문서는 curve model과 fixed-bias field-map model에서 무엇을 비교하고,
어떤 전처리·입력 변수·모델 변수를 선택했으며, validation/test에서 어떤
결과가 나왔는지를 한곳에 정리한다. 수치는 저장된 JSON/Markdown 보고서와
최종 checkpoint에서 가져왔다. Test는 모델 선정에 사용하지 않았다.

핵심 근거 파일:

- Curve 설정: `ai/curve_model/configs/baseline.json`,
  `configs/pca_xgboost_final.json`, `configs/preprocessing/selected_legacy.json`
- Curve 수치: `ai/model_artifacts/curve_model/optimization/baselines/`의
  `baseline_comparison.md`와 세 모델의 `evaluation/validation_report.json`,
  final package의 `selection_report.json`, `metrics.json`, `final_test_summary.json`
- Field-map 전처리: `ai/field_map_model/configs/selected_preprocessing.json`
- Field-map 수치: final package의 `selection_report.json`,
  `final_test_report.json`, node/element target-transform JSON

## 1. 공통 평가 원칙

- 동일한 device-level split을 두 모델에서 재사용했다.
- Device 수는 train 1,802 / validation 386 / test 386이다.
- 전처리, 모델 계열, 하이퍼파라미터는 validation으로만 선택했다.
- 선택된 모델을 고정한 뒤 test를 한 번 평가했으며 재학습하지 않았다.
- 오류가 큰 정상 샘플을 제거하여 성능을 높이는 방식은 사용하지 않았다.
- 과거 restricted-domain 실험은 coverage를 97.98%, 82.67%로 줄여 수치를
  개선한 것이므로 폐기했다. 최종 curve model은 전체 prepared domain을 쓴다.

## 2. Curve model

### 2.0 실제 진행 순서

코드, 최종 config와 당시 채팅에 남아 있는 작업 순서를 합치면 실제 flow는
다음과 같다.

1. Device-level split, 입력 변수, 평가 지표를 고정했다.
2. IdVg/IdVd의 물리 기반 target-transform 후보를 만들었다.
3. Residual MLP를 빠른 screening 모델로 사용해 후보를 줄였다.
4. 남은 transformer를 PCA+XGBoost, Residual MLP, Shared encoder baseline에
   모두 적용해 특정 MLP에만 유리한 전처리가 아닌지 확인했다.
5. 이 비교에서 물리 기반 신규안 대신 기존 transformer를 공통안으로 선택했다.
6. Train에서 voltage coordinate별 scaler를 fit하고 inverse-transform까지
   하나의 전처리 계약으로 고정했다.
7. 동일한 전처리와 split으로 세 model family baseline을 비교했다.
8. 가장 좋은 PCA+XGBoost만 PCA component와 XGBoost를 최적화했다.
9. Seed 42/43/44 validation으로 개선의 안정성을 확인하고 seed 42
   `refine_01`을 잠갔다.
10. 잠근 모델을 재학습하지 않고 test에서 한 번 평가했다.

초기 transformer screening 후보들의 모든 이름·수식·수치표가 보존된 것은
아니다. 그러나 구버전 transformer를 최종 공통 전처리로 승격한 뒤 다시 계산한
세 model-family baseline의 최종 validation 보고서는 로컬 실행 기록에서 원문을
복구했다. 아래 수치는 추정이나 재학습 결과가 아니라 당시 생성된 JSON과 비교표의
원래 값이다.

### 2.1 문제 정의와 입력

```text
[L, T, log10(B), log10(SD), log10(LDD), fixed bias]
  -> IdVd 101 points 또는 IdVg 135 points
```

IdVd와 IdVg는 voltage grid와 dynamic range가 달라 별도 가중치를 사용한다.
IdVd는 고정 `Vg=1.5, 3.0 V`, IdVg는 고정 `Vd=0.05, 1.5 V`를 생성한다.

### 2.2 검토한 모델과 전처리

검토한 세 모델 계열은 다음과 같다.

1. PCA + XGBoost
2. Residual multi-output MLP
3. Shared encoder + separate heads

세 baseline 비교에서 PCA + XGBoost가 최종 최적화 대상으로 선택됐다. 아래
평가는 train 1,802개로 학습하고 동일한 validation device 386개 전체를 사용한
결과이며 test는 사용하지 않았다. 모든 selection score는 낮을수록 좋다.

| 순위 | 모델 | Combined score | IdVd score | IdVg score | 전기 파라미터 추출 성공 | 전기 파라미터 P50 score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | PCA + XGBoost | 0.037441 | 0.021639 | 0.053243 | 386/386 (100.0%) | 0.363762 |
| 2 | Shared encoder | 0.061622 | 0.049889 | 0.073356 | 199/386 (51.6%) | 7.67034 |
| 3 | Residual MLP | 0.070224 | 0.069107 | 0.071341 | 127/386 (32.9%) | 6.77524 |

Selection score를 구성하는 tail 지표의 상세값은 다음과 같다.

| 모델 | IdVd P95 NRMSE | IdVd P95 decade MAE | IdVg P95 NRMSE | IdVg P95 decade MAE |
|---|---:|---:|---:|---:|
| PCA + XGBoost | 0.0189728 | 0.0106654 | 0.0164715 | 0.0515955 |
| Shared encoder | 0.0436869 | 0.0248066 | 0.0326470 | 0.0700908 |
| Residual MLP | 0.0594031 | 0.0388153 | 0.0481591 | 0.0665253 |

각 baseline validation report에 저장된 전체 curve의 선형 오차와 결정계수는
다음과 같다.

| 모델 | IdVd MAE | IdVd RMSE | IdVd R² | IdVg MAE | IdVg RMSE | IdVg R² |
|---|---:|---:|---:|---:|---:|---:|
| PCA + XGBoost | 0.0381662 | 0.0937138 | 0.9998663 | 0.0199924 | 0.0713277 | 0.9996930 |
| Shared encoder | 0.1543052 | 0.4474634 | 0.9969522 | 0.0539647 | 0.1687701 | 0.9982811 |
| Residual MLP | 0.2099446 | 0.5020671 | 0.9961629 | 0.0776132 | 0.2645029 | 0.9957779 |

전기 파라미터 종합오차의 분포도 모델 선택을 뒷받침한다.

| 모델 | 유효 개수 | Mean | Std | P50 | P90 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PCA + XGBoost | 386 | 0.591578 | 0.775953 | 0.363762 | 1.240909 | 1.543339 | 3.320330 | 9.635518 |
| Shared encoder | 199 | 8.500855 | 4.819462 | 7.670335 | 13.547321 | 15.534901 | 27.861857 | 32.341324 |
| Residual MLP | 127 | 7.585813 | 4.265838 | 6.775242 | 14.297543 | 15.632292 | 17.166377 | 17.966220 |

PCA+XGBoost 선택은 Combined score가 Shared encoder보다 39.2%, Residual
MLP보다 46.7% 낮았고, IdVd와 IdVg score 모두 세 모델 중 최저였다는 정량적
결과에 따른 것이다. 전기 파라미터도 유일하게 386개 전부 추출에 성공했다. 구조적
관점에서도 이 데이터와 잘 맞는다. 한 I-V curve의 인접 voltage 값들은 강하게
상관되어 있어 PCA로 적은 coefficient에 압축할 수 있고, XGBoost는 1,802개
train device 규모의 tabular 구조·도핑 입력에서 비선형 상호작용을 안정적으로
학습할 수 있다. Residual MLP는 전체 curve를 직접 출력하는 유연성이 있지만
동일 데이터 규모의 baseline에서 PCA+XGBoost보다 모든 주요 curve 오차가 컸고,
shared encoder는
IdVd/IdVg의 grid·dynamic range·유효 transform이 달라 공통 표현의 이득보다
negative transfer 가능성이 있었다. 이 설명은 모델 구조의 물리적/통계적
해석이며, 최종 선택 자체는 validation 정량평가로 결정했다.

물리 기반 신규 transformer와 기존 transformer를 세 모델의 full-domain
validation에서 비교했고, 신규 transformer는 특히 IdVg 저전압 log curve의
형상을 불안정하게 만들어 기각했다. 최종 선택은
`selected_legacy_transformer_v1`이다.

Curve target 처리와 transformer는 서로 구분된다.

- 원본 배열은 덮어쓰지 않고 학습 target 사본만 정리한다.
- IdVg target은 `1e-10 mA/um` 미만을 TCAD resolution floor로 제한한다.
- IdVd는 `Vd=0` 경계점만 정확히 0으로 둔다.
- IdVd, `Vg=1.5 V`: signed-log, scale `1e-3 mA/um`
- IdVd, `Vg=3.0 V`: asinh, scale `1e-3 mA/um`
- IdVg: signed-log, scale `1e-10 mA/um`
- 모든 target은 voltage coordinate별 scaler를 사용한다.
- Transformer 내부 `noise_floor`는 0이며 별도의 추가 clipping은 없다.

최종 nonlinear transform 수식은 다음과 같다.

```text
signed_log(I; s) = sign(I) * log(1 + |I| / s)
asinh_transform(I; s) = asinh(I / s)
```

두 식 모두 `|I| << s`에서는 거의 선형이므로 작은 변화와 부호를 보존하고,
`|I| >> s`에서는 로그처럼 압축하여 큰 on-current가 loss를 독점하지 않게 한다.
Signed-log는 양·음 전류를 대칭적으로 다루며, asinh는 0에서 매끄럽고 역변환이
안정적이다. 최종 IdVd가 bias-separated transform을 쓰는 이유는 `Vg=1.5 V`와
`3.0 V` curve의 전류 분포와 tail 특성이 서로 달랐기 때문이다. 따라서 메모의
“IdVd asinh에서 signed-log 하나로 변경”은 최종 상태와 다르다.

Per-coordinate standard scaling은 transform된 각 voltage point `k`에 대해
train set에서만 평균과 표준편차를 fit한다.

```text
z_k = (transform(I_k) - mean_k) / std_k
inverse: I_k = inverse_transform(z_k * std_k + mean_k)
```

이 방식은 off/subthreshold/on 구간의 서로 다른 분산을 맞춰 특정 voltage
구간이 loss를 지배하는 것을 줄인다. 질문에 적힌 “6개 전처리”는 실제로
floor, IdVg 식/scale, bias별 IdVd 식/scale, scaler, inverse를 하나의 계약으로
묶어 부른 것이며 항목 개수를 엄밀히 6개로 제한한 것은 아니다.

IdVd에만 다음 물리 파생 입력을 추가했다. IdVg에서는 validation상 이득이
확정되지 않아 원래 6개 입력만 사용했다.

```text
1/L, 1/T, L/T,
log10(SD)-log10(B), log10(LDD)-log10(B), log10(SD)-log10(LDD)
```

Tail weighting은 IdVd `Vg=1.5 V` 후보로 검토했지만 validation tail score가
나빠져 최종적으로 사용하지 않았다.

### 2.3 PCA와 XGBoost 최적화

PCA component 후보는 `4, 8, 12, 16, 20, 24, 28, 32`였다. 선택 결과는:

| Curve | 선택 component | 선택 이유 |
|---|---:|---|
| IdVd, Vg=1.5 V | 8 | tail score 0.424732로 후보 중 최저 |
| IdVd, Vg=3.0 V | 8 | tail score 0.103459로 후보 중 최저 |
| IdVg | 28 | tail score 0.244525로 후보 중 최저; 32보다도 근소하게 우수 |

최종 모델 객체는 최대 32 components를 보관하고 위 개수만 active component로
사용한다. 모든 curve에 `n_estimators=8000`, validation early stopping 200을
적용했다. 학습된 booster에서 확인한 최종 resolved 값은 다음과 같다.

| XGBoost 변수 | 최종 적용값 | 설정 방식 |
|---|---:|---|
| max_depth | 5 | 모델 코드 기본값 |
| learning_rate | 0.03 | 모델 코드 기본값 |
| subsample | 0.85 | 모델 코드 기본값 |
| colsample_bytree | 0.90 | 모델 코드 기본값 |
| min_child_weight | 1 | XGBoost 기본값 |
| reg_lambda | 1 | XGBoost 기본값 |
| reg_alpha | 0 | XGBoost 기본값 |
| n_estimators | 8000 | 최종 config override |
| early_stopping_rounds | 200 | 최종 config override |
| objective | reg:squarederror | 모델 코드 기본값 |
| eval_metric | RMSE | 모델 코드 기본값 |
| tree_method | hist | 모델 코드 기본값 |

초기 탐색 공간에는 max depth 3/5/7, learning rate 0.02/0.03/0.05,
row/column subsampling, child weight, L1/L2 regularization이 포함됐다. 최종 저장
객체의 명시적 override는 tree 수와 early stopping이며, 나머지는 모델 코드와
XGBoost의 고정 기본값을 사용한다.

각 bias model은 32개 PCA coefficient regressor를 학습해 저장했지만 inference는
IdVd에서 앞의 8개, IdVg에서 앞의 28개만 활성화한다. Early stopping으로 각
coefficient의 실제 best iteration은 서로 다르며, 8,000은 상한이다.

### 2.4 Validation 선택 결과

Curve 선택 score는 평균 오차만 낮추는 모델보다 worst-tail에서 안정적인 모델을
고르기 위해 미리 다음과 같이 고정했다.

```text
IdVd score = P95(NRMSE) + 0.25 * P95(decade MAE)
IdVg score = P95(decade MAE) + 0.10 * P95(NRMSE)
Combined score = (IdVd score + IdVg score) / 2
```

NRMSE는 curve RMSE를 해당 target curve의 최대 절대 전류로 나눈 값이다.
Decade MAE는 `log10(max(|I|, 1e-10))` 공간의 curve별 MAE다. IdVg는 여러
decade의 subthreshold 정확도가 핵심이므로 decade MAE 비중이 크고, IdVd는
선형 curve 형상과 amplitude 정확도를 더 크게 반영한다.

Seed 42 기준 baseline과 최적화 모델 비교:

| 지표 | Baseline | 최적화 | 개선 |
|---|---:|---:|---:|
| Combined score | 0.037441 | 0.035704 | 4.64% |
| IdVd score | 0.021639 | 0.021062 | 2.67% |
| IdVg score | 0.053243 | 0.050346 | 5.44% |
| 전기 파라미터 추출 | 386/386 | 386/386 | 유지 |
| 전기 파라미터 normalized P50 | 0.363762 | 0.315906 | 13.16% |

Curve 종류별 상세 validation 변화:

| Curve/지표 | Baseline | 최적화 | 개선 |
|---|---:|---:|---:|
| IdVd linear MAE | 0.038166 | 0.036585 | 4.14% |
| IdVd linear RMSE | 0.093714 | 0.090751 | 3.16% |
| IdVd P95 NRMSE | 0.018973 | 0.018444 | 2.78% |
| IdVd P95 decade MAE | 0.010665 | 0.010469 | 1.84% |
| IdVd maximum decade MAE | 1.533536 | 1.533341 | 0.01% |
| IdVg linear MAE | 0.019992 | 0.018536 | 7.28% |
| IdVg linear RMSE | 0.071328 | 0.065749 | 7.82% |
| IdVg P95 NRMSE | 0.016471 | 0.015453 | 6.18% |
| IdVg P95 decade MAE | 0.051596 | 0.048801 | 5.42% |
| IdVg maximum decade MAE | 0.743705 | 0.731131 | 1.69% |

Seed 42/43/44 모두 최적화 모델이 baseline보다 좋았다. 3-seed 평균 score는
0.039429에서 0.037869로 3.96% 개선됐다. 최종 선택은 seed 42의 `refine_01`이다.

| Seed | Baseline score | 최적화 score | 개선 |
|---:|---:|---:|---:|
| 42 | 0.037441 | 0.035704 | 4.64% |
| 43 | 0.040609 | 0.039824 | 1.93% |
| 44 | 0.040237 | 0.038079 | 5.36% |

### 2.5 한 번의 최종 test

| 지표 | Locked validation | Final test | 변화 |
|---|---:|---:|---:|
| Combined score | 0.035704 | 0.048049 | +34.57% |
| IdVd score | 0.021062 | 0.023838 | +13.18% |
| IdVg score | 0.050346 | 0.072259 | +43.52% |
| 전기 파라미터 추출 | 386/386 | 386/386 | 유지 |

| Curve/지표 | Locked validation | Final test | 변화 |
|---|---:|---:|---:|
| IdVd linear MAE | 0.036585 | 0.037400 | +2.23% |
| IdVd linear RMSE | 0.090751 | 0.098402 | +8.43% |
| IdVd P95 NRMSE | 0.018444 | 0.020784 | +12.68% |
| IdVd P95 decade MAE | 0.010469 | 0.012217 | +16.70% |
| IdVd maximum decade MAE | 1.533341 | 2.350210 | +53.27% |
| IdVg linear MAE | 0.018536 | 0.017246 | -6.96% |
| IdVg linear RMSE | 0.065749 | 0.063695 | -3.13% |
| IdVg P95 NRMSE | 0.015453 | 0.016317 | +5.59% |
| IdVg P95 decade MAE | 0.048801 | 0.070627 | +44.72% |
| IdVg maximum decade MAE | 0.731131 | 0.625528 | -14.44% |

Test에서 IdVg tail error 증가가 가장 큰 일반화 한계로 남았다. 반면 IdVg
linear MAE와 RMSE는 validation보다 각각 6.96%, 3.13% 낮았다. 즉 평균 선형
curve 오차보다 저전류/log-tail 오차가 주요 향후 개선 대상이다.

최종 모델: `PCA + XGBoost`, full domain, seed 42.

### 2.6 별도 메모의 교정 요약

| 메모 내용 | 판정 | 최종 기록 |
|---|---|---|
| Train/validation/test = 1,802/386/386, seed 42 | 맞음 | Device-level stratified split |
| Residual MLP로 transformer 빠른 screening | 맞음 | 이후 세 model family에 다시 적용해 공통성 확인 |
| IdVg floor-aware log1p에서 signed-log로 변경 | 표현 수정 필요 | Target cleaning floor `1e-10`과 signed-log transform은 별도 단계이며 최종 transform은 signed-log, scale `1e-10` |
| IdVd asinh에서 signed-log로 변경 | 틀림 | Vg=1.5는 signed-log, Vg=3.0은 asinh인 bias-separated 방식 |
| Per-coordinate scaler 선택 | 맞음 | 각 voltage point의 train mean/std 사용 |
| IdVd PCA 8, IdVg PCA 28 | 보완 필요 | IdVd의 두 고정 Vg가 각각 8, IdVg가 28 |
| max_depth 5, learning_rate 0.03, subsample 0.85, colsample 0.9 | 맞음 | 저장 booster에서 확인 |
| min_child_weight 1, lambda 1, alpha 0 | 값은 맞음 | 별도 탐색 override가 아니라 최종 XGBoost 기본 적용값 |
| n_estimators 8000, early stopping 200 | 맞음 | 8,000은 상한이며 component마다 실제 best iteration은 다름 |
| Test 1회 평가 | 맞음 | Model lock 후 재학습 없이 386 test device 평가 |

## 3. Field-map model

### 3.1 범위와 입력/출력

Field-map은 현재 `Vg=3 V, Vd=3 V` 한 동작점만 지원한다. 새 구조마다 Gmsh가
region-labelled triangle mesh를 생성하고 coordinate MLP가 가변 개수의 node와
element에 값을 채운다.

전역 입력:

```text
L_nm, Tox_nm, log10(B), log10(SD), log10(LDD)
```

각 좌표의 입력은 normalized x/y, channel-relative x, y in um, bulk/oxide/gate
one-hot region, analytic local NetDoping이다. 최종 feature 수는 15개다.
NetDoping은 `.dat` target을 예측하는 항목이 아니라 구조·도핑 식으로 계산되는
known local input이다.

출력은 node와 element를 분리했다.

- Node model: Potential, Electrons, Holes, USRH
- Element model: ElectricField x/y, ElectronCurrent x/y, HoleCurrent x/y

### 3.2 전처리 선택

Coordinate ExtraTrees screening을 seed 42와 123에서 수행했고 test는 열지 않았다.

| Domain | 선택 recipe | 선택 평균 | 차점 recipe | 차점 평균 |
|---|---|---:|---|---:|
| Node | signed-log q10 + standard | 0.025864 | asinh q10 + standard | 0.026001 |
| Element | asinh q10 + standard | 0.440966 | signed-log q10 + standard | 0.441081 |

실제 field별 transform은:

- Potential: identity
- Electrons/Holes: log1p, train-only positive q10 scale, inverse 후 0 이상 제한
- USRH: signed-log1p, train-only absolute q10 scale
- 모든 E/J component: asinh, train-only absolute q10 scale
- 각 field마다 독립 standard scaler, train에서만 fit
- NetDoping: signed-log1p, scale `1e15 cm^-3`

물리적 이유는 field마다 다르다. Potential은 부호를 포함하지만 dynamic range가
제한적이고 Poisson solution이 비교적 매끄러워 identity가 적합하다. Carrier
density는 음수가 될 수 없고 여러 decade에 걸치므로 log1p가 적합하다. USRH는
generation/recombination 방향에 따라 부호가 바뀔 수 있어 signed-log가 필요하다.
Electric field와 current density의 x/y component도 방향 때문에 부호를 보존해야
하며 크기 범위가 넓으므로 0 근처에서 선형이고 큰 값에서 로그형인 asinh를 쓴다.

Node와 element model을 분리한 이유도 TCAD discretization을 보존하기 위해서다.
Potential/carrier/SRH는 mesh node에 정의되고, E/J component는 triangle element에
정의된다. 임의로 모두 node grid로 보간하면 interface와 conservation 관련 정보가
변할 수 있으므로 원래 저장 위치에서 각각 학습했다.

작은 solver 값은 삭제하거나 target에서 잘라내지 않았다. Resolution floor는
후보가 numerical noise를 확대해 유리해지는 것을 막기 위한 공통 평가 지표에만
사용했다.

### 3.3 Baseline architecture와 학습 변수

Node/element 모두 coordinate residual MLP를 사용했다.

| 변수 | 값 |
|---|---:|
| Input size | 15 |
| Hidden width | 192 |
| Residual blocks | 4 |
| Dropout | 0 |
| Activation | SiLU |
| Normalization | LayerNorm |
| Batch size | 4096 |
| Maximum epochs | 100 |
| Learning rate | 0.001 |
| Weight decay | 1e-5 |
| Train samples | 129,744/domain |
| Validation samples | 37,056/domain |

Device와 region별 동일한 수를 sampling했다. Baseline validation score는 node
0.030509, element 0.454175였다. 최종 node model은 이 baseline checkpoint를
그대로 사용했다.

### 3.4 Element model 개선과 선택

Element model에는 세 후보가 있었다.

1. 원래 coordinate MLP baseline
2. Bulk/channel-focused sampling과 field loss weighting
3. 2번 + electric-field 방향 physics loss

최종 physics 후보의 field loss weight는 Ex 1.06154, Ey 1.01538,
Jnx 0.83077, Jny 1.43077, Jpx 0.78462, Jpy 0.87692이고, E 방향 cosine loss
weight는 0.03이다.

386개 validation full map 비교:

| Field | Baseline | Bulk-focused | Bulk + physics | Physics 개선률 |
|---|---:|---:|---:|---:|
| ElectricField_x | 0.651389 | 0.437035 | 0.439065 | 32.60% |
| ElectricField_y | 0.348235 | 0.264777 | 0.273125 | 21.57% |
| ElectronCurrent_x | 0.154326 | 0.132678 | 0.141722 | 8.17% |
| ElectronCurrent_y | 1.011172 | 0.682837 | 0.684520 | 32.30% |
| HoleCurrent_x | 0.594806 | 0.526779 | 0.529193 | 11.03% |
| HoleCurrent_y | 0.650954 | 0.416180 | 0.418929 | 35.64% |

Bulk-focused가 field RMSE만 보면 조금 더 좋지만 E-direction cosine은 baseline
0.750503, bulk-focused 0.716672, physics 0.873995였다. Physics 후보는 모든
element field에서 baseline을 개선하면서 방향 일관성을 크게 회복했기 때문에
`element_bulk_physics`를 선택했다.

Physics loss는 electrostatic 관계 `E ≈ -grad(V)`의 방향 cosine을 이용한다.
정확도 전용 bulk-focused 후보는 개별 field RMSE는 가장 낮았지만 E 방향 cosine이
baseline보다 오히려 낮았다. 최종 후보는 RMSE를 약간 양보하고도 방향 cosine을
0.873995까지 올렸으므로, 새로운 mesh에서 물리적으로 일관된 vector field를
만드는 데 더 적합하다고 판단했다. 다만 TCAD raw field와 potential gradient의
RMS scale 자체도 완전히 1:1이 아니므로 magnitude equality를 강제하지 않고
작은 weight 0.03의 방향 제약만 사용했다.

### 3.5 한 번의 최종 test

386 test device의 full-map evaluation-space mean RMSE:

| Field | Mean RMSE | Field | Mean RMSE |
|---|---:|---|---:|
| Potential | 0.033657 | ElectricField_x | 0.440756 |
| Electrons | 0.030915 | ElectricField_y | 0.273718 |
| Holes | 0.040289 | ElectronCurrent_x | 0.142019 |
| USRH | 0.052426 | ElectronCurrent_y | 0.682906 |
|  |  | HoleCurrent_x | 0.528935 |
|  |  | HoleCurrent_y | 0.417880 |

추가 검증 결과:

- Negative carrier prediction: 모든 device에서 0개
- Analytic NetDoping signed-log RMSE mean: 0.000121927
- Model E와 `-grad(V)` cosine mean: 0.873748
- Regenerated Gmsh mesh: 5,611 nodes / 10,481 triangles, 모든 출력 finite

현재 가장 큰 한계는 `ElectronCurrent_y`와 hole-current component 오차이며,
fixed bias 한 점만 지원한다는 것이다. 새 구조의 mesh point 개수는 달라도
추론할 수 있지만, 학습 parameter 범위 밖 입력은 extrapolation이다.

최종 모델: baseline node coordinate MLP + `element_bulk_physics` coordinate MLP.

## 4. 최종 배포 구성

- Curve: `ai/model_artifacts/curve_model/final/pca_xgboost/`
- Field map: `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/`
- Field-map GUI runtime: PyTorch checkpoint를 NumPy `model.npz`로 export해 사용하며,
  원 checkpoint와 transform-space RMSE `2.35e-7`로 일치함
- 통합 GUI: `ai/integrated_visualization_app.py`
- 실행 패키지 검사: `python ai/tools/check_runtime_package.py`
- 최종 test 결과는 보고용이며 모델 선택이나 재튜닝에 사용하지 않는다.

세부 원본 수치는 각 final package의 `selection_report.json`,
`final_test_report.json`, `metrics.json`, `preprocessing_config.json`을 기준으로 한다.
