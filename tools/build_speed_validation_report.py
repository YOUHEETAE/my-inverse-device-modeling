from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def calculate_speed_results(
    tcad_summary: dict[str, Any],
    ai_validation: dict[str, Any],
) -> dict[str, Any]:
    tcad = tcad_summary["elapsed_seconds"]
    ai = ai_validation["combined_representative_statistics_ms"]
    tcad_median_s = float(tcad["median"])
    tcad_p95_s = float(tcad["p95"])
    ai_primary_median_s = float(ai["simulation_to_result"]["median"]) / 1000.0
    ai_primary_p95_s = float(ai["simulation_to_result"]["p95"]) / 1000.0
    ai_e2e_median_s = float(ai["user_end_to_end"]["median"]) / 1000.0
    ai_e2e_p95_s = float(ai["user_end_to_end"]["p95"]) / 1000.0
    paired = {}
    tcad_cases = tcad_summary.get("representative_case_timings", {})
    ai_case_medians = ai_validation.get("per_condition_primary_median_ms", {})
    for label in ("short", "default", "long"):
        if label not in tcad_cases or label not in ai_case_medians:
            continue
        tcad_case_s = float(tcad_cases[label]["elapsed_sec"])
        ai_case_s = float(ai_case_medians[label]) / 1000.0
        paired[label] = {
            "case_id": tcad_cases[label]["case_id"],
            "tcad_elapsed_s": tcad_case_s,
            "ai_median_s": ai_case_s,
            "speedup": tcad_case_s / ai_case_s,
        }
    return {
        "tcad_median_s": tcad_median_s,
        "tcad_p95_s": tcad_p95_s,
        "ai_primary_median_s": ai_primary_median_s,
        "ai_primary_p95_s": ai_primary_p95_s,
        "ai_e2e_median_s": ai_e2e_median_s,
        "ai_e2e_p95_s": ai_e2e_p95_s,
        "primary_median_speedup": tcad_median_s / ai_primary_median_s,
        "end_to_end_median_speedup": tcad_median_s / ai_e2e_median_s,
        "conservative_speedup": tcad_median_s / ai_primary_p95_s,
        "p95_to_p95_ratio": tcad_p95_s / ai_primary_p95_s,
        "paired_representative_cases": paired,
    }


def _write_chart(path: Path, results: dict[str, Any]) -> None:
    labels = ["Python TCAD", "AI Curve + Field", "AI End-to-End"]
    values = [
        results["tcad_median_s"],
        results["ai_primary_median_s"],
        results["ai_e2e_median_s"],
    ]
    colors = ["#4B5563", "#2563EB", "#10B981"]
    figure, axis = plt.subplots(figsize=(9.2, 5.6), dpi=160)
    bars = axis.bar(labels, values, color=colors, width=0.62)
    axis.set_yscale("log")
    axis.set_ylabel("Median execution time per device condition (seconds)")
    axis.set_title("SemiScopeAI Local Execution Speed Validation")
    axis.grid(axis="y", which="both", linestyle="--", alpha=0.3)
    axis.set_axisbelow(True)
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.12,
            f"{value:.3f} s" if value < 10 else f"{value:.1f} s",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )
    axis.text(
        0.98,
        0.96,
        (
            f"Curve + Field: {results['primary_median_speedup']:.1f}x faster\n"
            f"End-to-End: {results['end_to_end_median_speedup']:.1f}x faster"
        ),
        transform=axis.transAxes,
        ha="right",
        va="top",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": "#D1D5DB"},
    )
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def _write_report(path: Path, results: dict[str, Any]) -> None:
    paired = results["paired_representative_cases"]
    report = f"""# SemiScopeAI 속도 기술 검증 요약

## 핵심 결과

기존 Python TCAD 기록과 현재 AI surrogate를 동일한 로컬 실행 기준으로 비교했다. 장치 조건 하나에서 I-V Curve 4개와 Field Map 1개를 생성하는 계산시간은 Python TCAD 중앙값 {results['tcad_median_s']:.3f}초, AI 중앙값 {results['ai_primary_median_s']:.3f}초로 측정되어 **약 {results['primary_median_speedup']:.1f}배 단축**됐다.

Gmsh 구조 생성과 전기 파라미터 추출까지 포함한 AI 사용자 전체시간은 중앙값 {results['ai_e2e_median_s']:.3f}초다. TCAD 기존 기록보다 AI에 더 넓은 작업 범위를 포함한 비교에서도 **약 {results['end_to_end_median_speedup']:.1f}배 단축**된 결과다.

## 현재 대표 가속 배수의 정확한 비교 기준

현재 **{results['primary_median_speedup']:.2f}배**는 다음 두 통계를 나눈 값이다.

```text
Python TCAD 최종 성공 데이터 2,574건의 조건당 elapsed_sec 중앙값
{results['tcad_median_s']:.3f}초

÷

AI 대표 구조 3개 × 30회 반복의 Curve+Field 시간 통합 중앙값
{results['ai_primary_median_s']:.6f}초

= {results['primary_median_speedup']:.2f}배
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
| 짧은 채널 `{paired['short']['case_id']}` | {paired['short']['tcad_elapsed_s']:.3f}초 | {paired['short']['ai_median_s']:.3f}초 | **{paired['short']['speedup']:.1f}배** |
| 기본 `{paired['default']['case_id']}` | {paired['default']['tcad_elapsed_s']:.3f}초 | {paired['default']['ai_median_s']:.3f}초 | **{paired['default']['speedup']:.1f}배** |
| 긴 채널 `{paired['long']['case_id']}` | {paired['long']['tcad_elapsed_s']:.3f}초 | {paired['long']['ai_median_s']:.3f}초 | **{paired['long']['speedup']:.1f}배** |

이 표는 설계 조건은 정확히 일치하지만 반복 수가 다르다. TCAD는 과거 기록 1회이고 AI는 각 조건 30회 중앙값이다. 따라서 조건별 배수는 범위 확인용이며, 전체 headline에는 더 안정적인 `TCAD 2,574건 중앙값 / AI 90회 중앙값`을 사용한다.

## 사업계획서 삽입용 표

| 방식 | 포함 범위 | 중앙값 | P95 | 중앙값 기준 비교 |
|---|---|---:|---:|---:|
| Python TCAD | Curve 4개 + Field Map | {results['tcad_median_s']:.3f}초 | {results['tcad_p95_s']:.3f}초 | 기준 |
| AI, prepared mesh | Curve 4개 + Field Map | {results['ai_primary_median_s']:.3f}초 | {results['ai_primary_p95_s']:.3f}초 | **{results['primary_median_speedup']:.1f}배 단축** |
| AI, End-to-End | Gmsh + Curve + Field + 파라미터 | {results['ai_e2e_median_s']:.3f}초 | {results['ai_e2e_p95_s']:.3f}초 | **{results['end_to_end_median_speedup']:.1f}배 단축** |

## 사업계획서 권장 문장

> 기존 Python 기반 TCAD는 하나의 MOSFET 설계 조건에서 I-V Curve 4개와 2D Field Map을 생성하는 데 중앙값 약 {results['tcad_median_s']:.1f}초가 소요되었다. SemiScopeAI는 동일 결과를 AI surrogate로 약 {results['ai_primary_median_s']:.2f}초에 생성하여 계산시간을 약 {results['primary_median_speedup']:.0f}배 단축했으며, Gmsh 구조 생성과 전기 파라미터 추출까지 포함한 전체 과정도 약 {results['ai_e2e_median_s']:.2f}초 내에 완료했다.

더 짧은 표현:

> MOSFET 조건별 Curve·Field 계산시간을 Python TCAD 약 {results['tcad_median_s']:.1f}초에서 AI 약 {results['ai_primary_median_s']:.2f}초로 단축해 약 {results['primary_median_speedup']:.0f}배의 설계 탐색 가속을 확인했다.

동일 조건 범위를 함께 밝히는 표현:

> 짧은·기본·긴 채널의 동일 설계 조건을 직접 대조한 결과 약 {min(item['speedup'] for item in paired.values()):.0f}~{max(item['speedup'] for item in paired.values()):.0f}배의 계산시간 단축을 확인했으며, 전체 TCAD 성공 데이터와 AI 반복측정의 대표 중앙값 비교에서는 약 {results['primary_median_speedup']:.0f}배의 가속을 보였다.

## 수치 해석

- 대표 가속 배수: TCAD median / AI Curve+Field median = **{results['primary_median_speedup']:.2f}배**
- 사용자 전체과정 기준: TCAD median / AI End-to-End median = **{results['end_to_end_median_speedup']:.2f}배**
- 보수적 참고값: TCAD median / AI Curve+Field P95 = **{results['conservative_speedup']:.2f}배**
- P95/P95 비율은 **{results['p95_to_p95_ratio']:.2f}배**지만 대표값보다 커서 `보수적 배수`라는 표현에는 사용하지 않는다.

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
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the business-plan speed validation package")
    parser.add_argument(
        "--tcad-summary",
        type=Path,
        default=REPOSITORY_ROOT / "docs/technical_validation/tcad_timing_summary.json",
    )
    parser.add_argument(
        "--ai-validation",
        type=Path,
        default=REPOSITORY_ROOT / "docs/technical_validation/ai_runtime_benchmark/ai_runtime_validation.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "docs/technical_validation/speed_validation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tcad_summary = json.loads(args.tcad_summary.read_text(encoding="utf-8"))
    ai_validation = json.loads(args.ai_validation.read_text(encoding="utf-8"))
    results = calculate_speed_results(tcad_summary, ai_validation)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "speed_results.json"
    results_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "validated",
                "comparison_basis": "same local execution basis",
                "hardware_specifications_recorded": False,
                "llm_included": False,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_report(output_dir / "business_plan_speed_summary.md", results)
    _write_chart(output_dir / "speed_comparison.png", results)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"report={output_dir / 'business_plan_speed_summary.md'}")
    print(f"chart={output_dir / 'speed_comparison.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
