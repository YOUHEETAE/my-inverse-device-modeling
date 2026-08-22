# TCAD–AI 500 nm 소자 비교 자료

## 최종 산출물

Curve와 Field Map을 별도 그림으로 구성했다. 두 그림 모두 왼쪽부터 `(a) 결과`, `(b) 결과`, `R² 값` 순서이며, 전체 제목과 하단 소자 조건 문장은 표시하지 않는다.

- `tcad_vs_ai_500nm_curves.png`, `.pdf`: Id–Vd와 Id–Vg 비교
- `tcad_vs_ai_500nm_fields.png`, `.pdf`: Potential과 Total current density 비교
- `tcad_vs_ai_500nm_metrics.json`: 모든 계산값과 표시 기준

## 대표 소자 선정

- Gate length: 500 nm
- Oxide thickness: 27 nm
- Bulk doping: 1e16 cm^-3
- Source/Drain doping: 1e20 cm^-3
- LDD doping: 1e18 cm^-3
- Dataset split: test

500 nm / 20 nm 조건은 학습 split에 속하므로 검증 그림에서 제외했다. 최종 그림은 실제 test split에 속하면서 나머지 도핑 조건이 같은 500 nm / 27 nm 소자를 사용한다.

## Curve 그림

### (a) Output characteristics

- Id–Vd, Vg=1.5 V와 3.0 V
- 각 curve는 동일한 101개 Vd point에서 비교
- R²는 선형 drain current 기준

### (b) Transfer characteristics

- Id–Vg, Vd=0.05 V와 1.5 V
- 각 curve는 동일한 135개 Vg point에서 비교
- 그래프와 R² 계산에 1e-10 mA/um current floor 적용
- R²는 log10 drain current 기준

TCAD는 밝은 실선, AI는 더 짙은 점선으로 표시한다. AI 점선을 TCAD 선보다 위에 그려 두 결과가 매우 가까운 경우에도 점선을 식별할 수 있게 했다.

### Curve R²

- Id–Vd, Vg=1.5 V: 0.99966
- Id–Vd, Vg=3.0 V: 0.99999
- Id–Vg, Vd=0.05 V: 0.99994
- Id–Vg, Vd=1.5 V: 0.99983

## Field Map 그림

Field 조건은 Vg=3.0 V, Vd=3.0 V다. 저장된 TCAD 원본 mesh를 사용하고 AI를 동일한 node 및 element 좌표에서 평가한다.

### (a) Potential

- TCAD 원본 Potential 값을 scalar-map 배경 이미지로 표시
- 동일한 Potential level에서 TCAD는 회색 실선, AI는 진한 적색 점선으로 표시
- R²는 전체 3,831개 node의 선형 Potential 값으로 계산
- Potential R²: 0.99939

### (b) Total current density

- 정의: `|Jn + Jp| = sqrt((Jn_x + Jp_x)^2 + (Jn_y + Jp_y)^2)`
- 단위: A/cm²
- 전도 전류가 물리적으로 정의되는 bulk semiconductor element만 사용
- 1e-10 A/cm² floor를 적용한 log scale 등고선
- TCAD 원본 Total current density를 scalar-map 배경 이미지로 표시
- 표시 범위는 TCAD 원본 값의 robust 1–99 percentile
- 등고선 표시에만 인접 element 값을 node로 평균하여 사용
- R²는 전체 bulk element의 log10 current density로 계산하며 percentile clipping은 적용하지 않음
- Total current density R²: 0.99419

## 해석 범위

이 값들은 그림에 사용한 단일 held-out test 소자의 결과다. 전체 모델의 일반 성능을 주장할 때는 최종 test report의 386개 test device 통계를 사용해야 한다.

Total current density의 선형 값은 매우 넓은 동적 범위를 가지므로 선형 R²가 기술적으로 유용하지 않다. 따라서 그래프의 log scale과 동일하게 log10 R²를 사용했고, 그림의 R² 패널에도 계산 기준을 명시했다.

## 재생성

기존 TCAD 데이터를 읽으므로 DEVSIM을 다시 실행하지 않는다.

```powershell
python tools/build_tcad_ai_evidence_figure.py
```
