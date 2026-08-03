# 모델 평가 재현 및 문서화 워크플로

이 문서는 `모델 자체를 바꾸지 않고`, 현재 저장된 결과/실행 산출물을 기준으로 AI 모델 평가를 다시 구성하거나, 필요한 경우 처음부터 다시 실행할 수 있도록 전체 흐름을 정리합니다.

## 목적

- curve model과 field-map model에 대해 처음부터 끝까지 재현 가능한 평가 흐름을 정리
- 최종 패키지와 보고서만 남아 있을 때도 재확인할 수 있는 단계 제공
- 누락된 intermediate 실행이 있다면 어떤 스크립트/파일을 다시 실행해야 하는지 명확히 표시
- `ai/MODEL_SELECTION_HISTORY.md`에 정리할 핵심 결과와 재현 정보를 확보

## 주요 산출물

- `ai/MODEL_SELECTION_HISTORY.md` : 최종 정리 문서
- `ai/MODEL_EVALUATION_WORKFLOW.md` : 현재 이 파일, 재현/검증 체크리스트 포함
- `ai/model_artifacts/curve_model/final/pca_xgboost/README.md` : curve 모델 요약
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/README.md` : field-map 모델 요약

## 전체 흐름 요약

1. 현황 점검
2. 데이터 준비
3. curve model baseline 비교 및 최종 모델 재현
4. field-map model preprocessing/model 재현
5. 최종 패키지 재생성 및 보고서 검증
6. 문서 작성 및 부족 항목 표시

## 1. 현황 점검

### 1.1. 최종 패키지와 보고서 확인

다음 파일/디렉터리를 우선 확인합니다.

- `ai/model_artifacts/curve_model/final/pca_xgboost/selection_report.md`
- `ai/model_artifacts/curve_model/final/pca_xgboost/final_test_report.md`
- `ai/model_artifacts/curve_model/final/pca_xgboost/final_test_summary.json`
- `ai/model_artifacts/curve_model/final/pca_xgboost/metrics.json`
- `ai/model_artifacts/curve_model/final/pca_xgboost/preprocessing_config.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/selection_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.json`
- `ai/5. Curve Model 보고서.pdf`

### 1.2. 재현 가능성 판단

- 위 파일이 모두 존재하면 문서화 우선
- 일부 보고서만 존재하면, 부족한 부분을 채우기 위해 필요한 재실행 단계 식별
- 최종 모델 아티팩트만 있고 보고서가 없으면, 결과 재현보다 실행/패키지 확인이 우선

## 2. 데이터 준비

### 2.1. curve model 데이터 준비

```powershell
python ai/curve_model/data/prepare_dataset.py
```

- 입력: repository root에서 실행
- 출력: `ai/model_artifacts/curve_model/dataset/curves.npz` 등
- 목적: 최종 모델 학습/평가에 사용된 curve dataset 생성

### 2.2. field-map model 데이터 준비

```powershell
python ai/field_map_model/data/prepare_dataset.py
```

- 출력: field-map HDF5 데이터셋
- 목적: field-map model training/validation/test 재현

## 3. Curve model 재현 및 검증

### 3.1. 최종 curve target preprocessing 확인

최종 전처리 설정은 `ai/curve_model/configs/preprocessing/selected_legacy.json`입니다.

- `IdVg`: `signed_log`, scale `1e-10 mA/um`
- `IdVd`: `bias_separated`
  - `Vg=1.5 V`: `signed_log`, scale `1e-3 mA/um`
  - `Vg=3.0 V`: `asinh`, scale `1e-3 mA/um`
- 모든 target은 voltage coordinate별 scaler를 사용
- `preprocessing_config.json`에 최종 선택이 기록됨
- `5. Curve Model 보고서.pdf`는 이 transformer와 score 설계가 validation-only 기준으로 선택된 과정을 문서화한다.
- PDF에서 확인 가능한 핵심 결정:
  - IdVg noise floor: `1e-10 mA/um`
  - IdVd Vd=0 경계: 정확히 0 고정
  - IdVd transform: `asinh` with P10 scale ×1.0
  - IdVg transform: `floor_log1p` with gm/Id knee ×1.0
  - Composite score: IdVg = P95 decade MAE + 0.1 × P95 NRMSE; IdVd = P95 NRMSE + 0.25 × P95 decade MAE
  - Scaler 최종 선택: `per-coordinate`가 global 대비 15.9% 더 낮은 통합 tail score를 기록함

### 3.2. 최종 PCA + XGBoost 재현

최종 선택 모델은 `ai/model_artifacts/curve_model/final/pca_xgboost`입니다.

이미 기록된 설정으로 다시 실행할 때는 다음을 사용합니다.

```powershell
python ai/curve_model/training/train_pca_xgboost.py \
  --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json \
  --component-candidates 4 8 12 16 20 24 28 32 \
  --seed 42 \
  --feature-engineering physical_v1 \
  --idvd-bias-separated \
  --tail-weighting false \
  --domain full \
  --report-test
```

- `--report-test`는 locked final test 결과를 생성할 때 사용
- 최종 validation 선택은 seed 42 기준이며, `refine_01` 모델을 고정
- 최종 package는 `ai/model_artifacts/curve_model/final/pca_xgboost/`에 저장

### 3.3. baseline 비교 재현 (필요할 때)

만약 baseline 비교가 재검증이 필요하면 다음 모델들도 함께 실행하여 비교합니다.

```powershell
python ai/curve_model/training/train_shared_encoder.py \
  --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json \
  --seed 42 \
  --device cpu \
  --report-test
```

```powershell
python ai/curve_model/training/train_residual_mlp.py \
  --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json \
  --kind both \
  --seed 42 \
  --device cpu \
  --report-test
```

- baseline 비교는 동일 transformer, 동일 split, 동일 validation device로 수행
- 결과는 `ai/model_artifacts/curve_model/optimization/baselines/` 또는 각 모델의 최종 `selection_report`에 기록될 수 있음

### 3.4. 핵심 검증 파일

- `ai/model_artifacts/curve_model/final/pca_xgboost/selection_report.md`
- `ai/model_artifacts/curve_model/final/pca_xgboost/final_test_report.md`
- `ai/model_artifacts/curve_model/final/pca_xgboost/evaluation/validation_report.json`
- `ai/model_artifacts/curve_model/final/pca_xgboost/evaluation/test_report.json`
- `ai/model_artifacts/curve_model/final/pca_xgboost/preprocessing_config.json`
- `ai/model_artifacts/curve_model/final/pca_xgboost/final_model_manifest.json`

## 4. Field-map model 재현 및 검증

### 4.1. 최종 field-map preprocessing 확인

최종 선택 설정은 `ai/field_map_model/configs/selected_preprocessing.json`입니다.

- node targets: `Potential` identity, `Electrons`/`Holes` log1p, `USRH` signed_log1p
- element targets: all `asinh`
- fixed-bias `Vg=3.0 V`, `Vd=3.0 V`
- train-only scale/target fitting

### 4.2. 최종 field-map 모델 재현

최종 package는 `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/`입니다.

기본 재실행 명령은 다음과 같습니다.

```powershell
python ai/field_map_model/training/train_coordinate_mlp.py \
  --preprocessing-config ai/field_map_model/configs/selected_preprocessing.json \
  --seed 42 \
  --report-test
```

- `--report-test`는 one-time final test를 다시 생성할 때 사용
- 최종 패키지는 `package_final_fieldmap_model.py`로 구성합니다

### 4.3. 최종 패키지 생성

최종 테스트가 완료되면 패키지 생성 명령을 실행합니다.

```powershell
python ai/field_map_model/tools/package_final_fieldmap_model.py
```

- 이 스크립트는 final-test 완료 마커를 확인하고, 최종 모델 체크포인트/스케일러/변환/보고서를 `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/`로 복사
- 이미 패키지가 존재하면 오류를 내므로, 패키지 재생성이 아닌 증거 확인만 할 때는 패키지를 그대로 사용

### 4.4. 추가 field-map 후보 재실행 (필요 시)

field-map 전처리 선택을 다시 검증해야 하면 다음 후보 스크립트도 실행할 수 있습니다.

```powershell
python -m ai.field_map_model.training.optimize_element_mlp
```

```powershell
python -m ai.field_map_model.training.optimize_element_physics
```

- 이 후보들은 최종 physics element 모델을 만드는 과정의 일부분
- 최종 패키지 `coordinate_mlp_physics`는 `element_bulk_physics` 후보를 기반으로 생성됨

### 4.5. 핵심 검증 파일

- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/selection_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.md`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_test_report.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/preprocessing_config.json`
- `ai/model_artifacts/field_map_model/final/coordinate_mlp_physics/final_model_manifest.json`

## 5. 최종 보고서 재구성

### 5.1. 문서화 대상

`ai/MODEL_SELECTION_HISTORY.md`에 다음 항목을 채웁니다.

- curve model 최종 전처리/transform selection
- curve model baseline 비교 결과 및 최종 선택 이유
- curve model 최종 test 결과와 validation-to-test 변화
- field-map 모델 최종 preprocessing 선택 근거
- field-map 모델 최종 test 결과 및 validation-to-test 변화
- 재현에 사용된 스크립트와 파일 경로
- 만약 재실행이 필요하거나 누락된 파일이 있다면 그 목록

### 5.2. 재현/결과 분리

- `selection_report.md`와 `validation_report.json`은 validation selection 근거
- `final_test_report.md`와 `final_test_summary.json`은 잠금된 test 결과
- `preprocessing_config.json`은 최종 transform 계약
- `final_model_manifest.json` 또는 `FINAL_TEST_COMPLETED.json`은 reproducibility marker

## 6. 체크리스트

- [ ] 최종 패키지가 존재하면 그 경로와 파일 목록을 확인
- [ ] 위에서 언급된 핵심 report 파일이 모두 존재하는지 점검
- [ ] 누락된 report가 있으면 사용자에게 재실행 필요 항목으로 명시
- [ ] 재실행할 경우 사용한 커맨드, seed, preprocessing config를 문서에 기록
- [ ] 문서 작성 중 모델 weight나 test 데이터를 변경하지 않음

## 7. 재실행 판단 기준

- `ai/model_artifacts/*/final/*` 패키지가 온전하고 보고서가 모두 존재하면: `재실행 불필요`, 문서화 우선
- `최종 report는 없지만 모델 패키지/스크립트가 남아 있으면`: `재실행 가능`, 문서화 + 재현 명령 기록
- `결과만 있고 재생성 스크립트가 없거나 실행환경이 불명확하면`: `문서화 중심`, 필요한 경우 우선 소스/환경부터 재구성

## 8. 재생성 실행 순서 예시

1. `python ai/curve_model/data/prepare_dataset.py`
2. `python ai/field_map_model/data/prepare_dataset.py`
3. `python ai/curve_model/training/train_pca_xgboost.py --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json --component-candidates 4 8 12 16 20 24 28 32 --seed 42 --feature-engineering physical_v1 --idvd-bias-separated --tail-weighting false --domain full --report-test`
4. `python ai/curve_model/training/train_shared_encoder.py --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json --seed 42 --report-test`
5. `python ai/curve_model/training/train_residual_mlp.py --preprocessing-config ai/curve_model/configs/preprocessing/selected_legacy.json --kind both --seed 42 --report-test`
6. `python ai/field_map_model/training/train_coordinate_mlp.py --preprocessing-config ai/field_map_model/configs/selected_preprocessing.json --seed 42 --report-test`
7. `python ai/field_map_model/tools/package_final_fieldmap_model.py`

> 이 순서대로 실행하면 1) 데이터 준비, 2) curve 모델 selection 및 locked test, 3) field-map locked test, 4) field-map final 패키지 생성까지 재현할 수 있습니다.

---

## 9. 현재 상태 요약

현재 저장소에는 다음 최종 증거 파일이 모두 존재합니다.

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

따라서 현재 단계에서는 재실행 없이 문서화와 최종 기록 검증이 완료 단계입니다. `MODEL_SELECTION_HISTORY.md`와 `MODEL_EVALUATION_WORKFLOW.md`가 함께 다음 내용을 신뢰의 근거로 제공합니다:

- 최종 curve preprocessing 계약과 validation-only selection 규칙
- 최종 test 한 번만 수행한 locked 평가 결과
- final report와 PDF의 일관된 score 정의 및 transform/scale 결정
- field-map 최종 selection과 test report 증거

이 문서는 결과만 남아 있는 상태에서도 history를 신뢰할 수 있도록, 현황 점검 → 필요 시 재실행 → 최종 문서화까지 완전한 검증 워크플로를 제공합니다.
