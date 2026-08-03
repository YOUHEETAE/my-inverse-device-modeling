# 6단계 — UI 통합, 토큰 최적화, 최종 검증

## UI 통합

- I-V와 Field 자동 설명 상단에 현재 분석 유형을 표시한다.
  - `SINGLE`: 단일 조건
  - `PAIR`: 한 변수 통제 비교
  - `COMPOUND`: 두 개 이상 입력 변수가 함께 바뀐 비교
  - `SWEEP`: 한 변수의 3개 이상 조건
  - `GROUP`: 여러 종류의 비교가 섞인 실험군
- 현재 기준 Curve와 변화 변수/스윕 범위를 항상 표시한다.
- Field는 전체 조건을 분석하되 화면에 그리는 대표 pair도 함께 표시한다.
- 기준 Curve를 바꾸면 자동 설명, Prompt Preview, I-V/Field 자유 질문
  스냅샷과 Field 대표 pair가 모두 같은 순서를 사용한다.
- 자동 설명과 질문 답변은 기존 `ScrolledText(wrap=WORD)`를 유지하여 긴
  문장이 오른쪽에서 잘리지 않고 세로 스크롤된다.

## LLM context 정책

- 자동 설명은 기존처럼 결정론적 분석 결과를 한 번만 Groq에 보내 문장
  교정을 수행한다.
- 자유 질문의 다중 조건 context는 all-pairs 원시 데이터를 보내지 않는다.
  - Sweep은 정렬된 인접 pair와 Python에서 계산한 추세만 전달한다.
  - 혼합 실험군은 planner가 선택한 통제 비교를 우선하며 최대 4개 pair만
    전달한다.
  - 고정 파라미터는 Curve마다 반복하지 않고 `fixed_conditions` 한 곳에
    분리한다.
  - 각 Curve에는 실제로 달라진 파라미터만 `varied_parameters`로 전달한다.
  - 일반 이론 검색 결과는 질문 답변에 필요한 4개 개념으로 제한한다.
- 2차 답변 생성 실패 후 같은 질문을 재시도하면 성공한 1차 의도 checkpoint를
  그대로 재사용하는 기존 정책을 유지한다.

3-condition sweep fixture에서 JSON context만 비교한 결과, legacy-like pack보다
I-V는 약 10%, Field는 약 12% 작아졌다. 실제 API token 절감률은 질문, 근거 수,
모델 tokenizer에 따라 달라지며 조건 수가 늘수록 all-pairs 제거 효과가 커진다.

## 검증 명령

```powershell
python -m pytest -q
python tests\run_all.py
python frontend\app.py --ui-smoke-test
python tools\case_study_smoke.py
python tools\oxide_case_smoke.py
```

검증 범위는 Case 1/2, I-V와 Field의 단일/쌍/3개 이상 조건, 통제 비교와
복합 비교의 주장 한계, 413/429/검증 실패 진단, 질문 checkpoint 재사용,
UI 위젯 생성과 긴 답변 스크롤을 포함한다. Live Groq 응답은 계정 한도와
네트워크 상태에 의존하므로 별도 환경 점검으로 남긴다.
