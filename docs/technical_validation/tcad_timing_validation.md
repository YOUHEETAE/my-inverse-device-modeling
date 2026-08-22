# Python TCAD 기존 실행시간 검증

## 결론

새 DEVSIM 시뮬레이션을 실행하지 않고 과거 `data_extraction` 기록을 재검산했다. 최종 채택된 2,574개 장치 조건에서 Python TCAD의 조건당 simulation-to-result 시간은 중앙값 143.642초, P95 400.908초다.

사업계획서의 기준 문구는 다음과 같이 제한한다.

> 동일한 로컬 실행 기준에서 기존 Python TCAD는 하나의 장치 조건에 대해 I-V Curve 4개와 최종 Field Map 1개를 생성하는 데 중앙값 약 143.6초가 소요되었다.

하드웨어 사양은 표시하지 않는다. LLM은 로컬 앱이 인터넷 기반 Groq API를 호출하는 구조이므로 이 시뮬레이션 시간에 포함하지 않는다.

## 원본 기록 검증

| 항목 | 결과 |
|---|---:|
| 기본 status 기록 | 2,691건 |
| 기본 성공 | 2,565건 |
| 기본 실패 | 126건 |
| 별도 재실행 성공 | 9건 |
| 기본 성공과 재실행 성공 중복 | 0건 |
| 최종 성공·고유 조건 | 2,574건 |
| 남은 최초 실패 조건 | 117건 |

별도 재실행 9건은 모두 최초 실패 조건을 복구한 결과다. 최종 성공 조건 수는 AI 학습 데이터와 dataset integrity report의 2,574건과 일치한다.

## 시간 통계

성공한 고유 조건 2,574건의 `elapsed_sec`를 사용했다. percentile은 nearest-rank 방식이다.

| 지표 | 시간 |
|---|---:|
| 최소 | 93.993초 |
| 중앙값 | **143.642초** |
| 평균 | 197.509초 |
| P90 | 383.484초 |
| P95 | **400.908초** |
| 최대 | 1,181.295초 |

조건별 시간을 더하면 508,388.934초, 약 141.22시간이지만, sweep은 병렬 job으로 실행되었으므로 이 합계를 실제 전체 wall-clock 시간으로 표현하지 않는다.

## 측정 경계

`tcad/data_extraction/tools/sweep_run.py:337-345`는 `gmsh_mos2d.py` subprocess 실행 직전부터 종료까지를 측정한다.

포함:

- DEVSIM 초기화
- Id-Vd 두 sweep
- Id-Vg 두 sweep
- subprocess 내부 수렴 재시도
- 최종 Field 계산과 Tecplot dump 생성

제외:

- 별도로 선행 생성한 Gmsh mesh
- subprocess 종료 후 Curve CSV 작성
- 전기 파라미터 추출
- 그래프 rendering
- LLM 설명 생성

따라서 다음 AI 단계의 주 비교값도 모델 로드와 mesh 생성을 제외한 Curve+Field 계산시간으로 맞춘다. Gmsh 생성부터 파라미터 추출까지의 AI 전체시간은 사용자 체감 보조지표로 별도 제시한다.

## 출력 완전성

- 조건별 Id-Vd 2개, 합계 202 points
- 조건별 Id-Vg 2개, 합계 270 points
- 조건별 총 472 I-V points
- 조건별 최종 Field Map 1개
- 현재 경로에서 확인한 출력 파일: 7,722개
- 누락 파일: 0개
- 빈 파일: 0개
- 완전한 Id-Vd/Id-Vg pair: 2,574개
- 전기 파라미터 추출 `ok`: 2,574개

status에는 한 조건 `L500T10|B1e17SD5e20LDD5e18`이 Id-Vd 201 points로 남아 있다. 현재 실제 CSV는 이후 재생성되어 101-point Id-Vd 두 개, 총 202 points이며 dataset integrity 검사도 canonical grid로 통과한다. 최종 자료에서는 현재 출력과 integrity report를 기준으로 한다.

## 다음 단계 입력값

- 대표 TCAD 기준: 143.642초
- 보수적 TCAD 기준: 400.908초
- 비교 출력: Curve 4개 + 472 I-V points + Field Map 1개
- AI 주 비교 경계: prepared mesh에서 Curve+Field 계산
- AI 보조 경계: Gmsh mesh + Curve + Field + 전기 파라미터 추출
