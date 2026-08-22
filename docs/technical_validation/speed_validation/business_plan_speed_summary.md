# SemiScopeAI 속도 기술 검증 요약

## 핵심 결과

기존 Python TCAD 기록과 현재 AI surrogate를 동일한 로컬 실행 기준으로 비교했다. 장치 조건 하나에서 I-V Curve 4개와 Field Map 1개를 생성하는 계산시간은 Python TCAD 중앙값 143.642초, AI 중앙값 0.904초로 측정되어 **약 158.9배 단축**됐다.

Gmsh 구조 생성과 전기 파라미터 추출까지 포함한 AI 사용자 전체시간은 중앙값 1.121초다. TCAD 기존 기록보다 AI에 더 넓은 작업 범위를 포함한 비교에서도 **약 128.1배 단축**된 결과다.

## 현재 대표 가속 배수의 정확한 비교 기준

현재 **158.87배**는 다음 두 통계를 나눈 값이다.

```text
Python TCAD 최종 성공 데이터 2,574건의 조건당 elapsed_sec 중앙값
143.642초

÷

AI 대표 구조 3개 × 30회 반복의 Curve+Field 시간 통합 중앙값
0.904146초

= 158.87배
```

따라서 이 값은 `동일한 한 조건을 159회 가속했다`는 의미가 아니다. TCAD는 전체 성공 데이터 분포의 중앙값이고, AI는 짧은·기본·긴 채널 대표 조건에 동일한 가중치를 부여한 90회 반복측정의 중앙값이다. 전체적인 로컬 계산시간 수준을 비교하는 **대표 통계 비교**다.

## 양쪽 측정 경계

| 구분 | Python TCAD | AI 주 비교 |
|---|---|---|
| 시작 상태 | Gmsh mesh가 파일로 준비됨 | 모델이 로드되고 mesh가 메모리에 준비됨 |
| Curve | Id-Vd 2개 + Id-Vg 2개 | Id-Vd 2개 + Id-Vg 2개 |
| I-V point | 202 + 270 = 472 | 202 + 270 = 472 |
| Field | DEVSIM Field 계산 | node + element Field 예측 |
| 초기화 | DEVSIM subprocess 및 solver 초기화 포함 | 모델 최초 로딩 제외 |
| 수렴 과정 | bias ramp와 convergence retry 포함 | iterative solver 없음 |
| 구조 생성 | 사전 Gmsh mesh 생성 제외 | prepared-mesh 비교에서는 제외 |
| 후처리 | Field Tecplot dump 포함, Curve CSV 작성 제외 | 결과가 메모리에 준비되는 시점, 파일 저장 제외 |
| 파라미터 추출 | 제외 | 주 비교에서는 제외 |
| LLM | 제외 | 제외 |

계산 결과의 종류와 bias/point 수는 대응하지만, 실행 파이프라인은 동일하지 않다. TCAD는 solver 초기화·수렴·Field dump를 포함하고 AI는 이미 로드된 surrogate에서 결과 배열을 생성한다. 따라서 `동일 solver benchmark`가 아니라 **기존 물리 시뮬레이션 workflow 대비 surrogate 결과 생성시간 비교**로 표현한다.

## 동일 조건 3건의 직접 대조

AI benchmark에 사용한 정확히 동일한 조건의 기존 TCAD 기록도 별도로 대조했다.

| 조건 | TCAD 기존 기록 | AI Curve+Field 중앙값 | 조건별 가속 배수 |
|---|---:|---:|---:|
| 짧은 채널 `L100T5|B5e16SD1e20LDD1e18` | 98.512초 | 0.877초 | **112.4배** |
| 기본 `L200T20|B1e16SD1e20LDD1e18` | 134.979초 | 0.731초 | **184.7배** |
| 긴 채널 `L1600T50|B1e16SD1e20LDD1e18` | 392.972초 | 1.426초 | **275.5배** |

이 표는 설계 조건은 정확히 일치하지만 반복 수가 다르다. TCAD는 과거 기록 1회이고 AI는 각 조건 30회 중앙값이다. 따라서 조건별 배수는 범위 확인용이며, 전체 headline에는 더 안정적인 `TCAD 2,574건 중앙값 / AI 90회 중앙값`을 사용한다.

## 사업계획서 삽입용 표

| 방식 | 포함 범위 | 중앙값 | P95 | 중앙값 기준 비교 |
|---|---|---:|---:|---:|
| Python TCAD | Curve 4개 + Field Map | 143.642초 | 400.908초 | 기준 |
| AI, prepared mesh | Curve 4개 + Field Map | 0.904초 | 1.734초 | **158.9배 단축** |
| AI, End-to-End | Gmsh + Curve + Field + 파라미터 | 1.121초 | 2.074초 | **128.1배 단축** |

## 사업계획서 권장 문장

> 기존 Python 기반 TCAD는 하나의 MOSFET 설계 조건에서 I-V Curve 4개와 2D Field Map을 생성하는 데 중앙값 약 143.6초가 소요되었다. SemiScopeAI는 동일 결과를 AI surrogate로 약 0.90초에 생성하여 계산시간을 약 159배 단축했으며, Gmsh 구조 생성과 전기 파라미터 추출까지 포함한 전체 과정도 약 1.12초 내에 완료했다.

더 짧은 표현:

> MOSFET 조건별 Curve·Field 계산시간을 Python TCAD 약 143.6초에서 AI 약 0.90초로 단축해 약 159배의 설계 탐색 가속을 확인했다.

동일 조건 범위를 함께 밝히는 표현:

> 짧은·기본·긴 채널의 동일 설계 조건을 직접 대조한 결과 약 112~276배의 계산시간 단축을 확인했으며, 전체 TCAD 성공 데이터와 AI 반복측정의 대표 중앙값 비교에서는 약 159배의 가속을 보였다.

## 수치 해석

- 대표 가속 배수: TCAD median / AI Curve+Field median = **158.87배**
- 사용자 전체과정 기준: TCAD median / AI End-to-End median = **128.09배**
- 보수적 참고값: TCAD median / AI Curve+Field P95 = **82.84배**
- P95/P95 비율은 **231.20배**지만 대표값보다 커서 `보수적 배수`라는 표현에는 사용하지 않는다.

## 측정 범위와 각주

1. Python TCAD 값은 기존 성공 데이터 2,574건의 기록이며 새 시뮬레이션을 실행하지 않았다.
2. AI 값은 짧은·기본·긴 채널 대표 조건 3개를 각각 5회 warm-up 후 30회 측정한 결과다.
3. 주 비교는 양쪽 모두 구조 mesh가 준비된 이후의 Curve+Field 계산시간이다.
4. AI End-to-End에는 Gmsh mesh 생성과 전기 파라미터 추출도 포함된다.
5. 모델 최초 로딩시간과 인터넷 기반 Groq LLM 응답시간은 시뮬레이션 가속 비교에서 제외했다.
6. 하드웨어 사양은 표시하지 않고 동일한 로컬 실행 기준의 기술 검증값으로 제시한다.

## 사용할 수 있는 주장과 피해야 할 주장

사용 가능:

- `기존 Python TCAD 기록 대비 대표 계산시간 약 159배 단축`
- `동일 대표 조건별 약 112~276배 가속`
- `구조 생성과 전기 파라미터 추출까지 포함해 약 1.12초`
- `Curve 4개, 472 I-V points와 Field Map을 생성하는 기준`

피해야 함:

- `동일 조건에서 정확히 159배`
- `상용 TCAD 대비 159배`
- `모든 설계 조건에서 159배`
- `동일한 물리 PC에서 측정됨`
- `LLM 설명까지 1.12초에 완료`

## 보고서 편집 시 권장 우선순위

본문에는 `143.6초 → 0.90초, 약 159배`와 출력 범위만 사용한다. 기술 검증 표에는 AI End-to-End 1.12초를 추가한다. 동일 조건 112~276배 범위와 측정 경계 차이는 각주 또는 기술 부록에 둔다.

## 근거 파일

- TCAD 집계: `docs/technical_validation/tcad_timing_summary.json`
- AI raw timing: `docs/technical_validation/ai_runtime_benchmark/ai_runtime_raw.csv`
- AI 검증 집계: `docs/technical_validation/ai_runtime_benchmark/ai_runtime_validation.json`
- 속도 계산값: `docs/technical_validation/speed_validation/speed_results.json`
