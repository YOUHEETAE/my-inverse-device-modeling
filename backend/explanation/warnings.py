from __future__ import annotations

from typing import Any

WARNING_TYPES = frozenset("""extrapolation multiple_parameter_change missing_data missing_subject missing_comparison missing_fixed_bias missing_curve_kind missing_region missing_mesh_connectivity missing_energy_band_cut invalid_numeric_value zero_denominator nonpositive_log_input unit_mismatch parameter_extraction_failed insufficient_curve_points insufficient_field_samples threshold_calculation_failed hotspot_detection_failed contour_analysis_failed connectivity_analysis_failed crowding_analysis_failed band_analysis_failed weak_visual_evidence conflicting_evidence no_meaningful_difference unsupported_analysis unsupported_field_display non_comparable_visual_scale model_approximation signed_value_ambiguity provider_unavailable provider_timeout provider_error invalid_provider_response response_schema_validation_failed legacy_payload cache_read_failed cache_write_failed cache_entry_invalid""".split())
SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
FALLBACK_ACTIONS = frozenset("""omit_affected_evidence omit_affected_evidence_and_include_caution reduce_claim_strength disable_cross_validation disable_tradeoff disable_numeric_output use_qualitative_only skip_comparison skip_subject return_partial_explanation return_safe_fallback request_user_data_check""".split())
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

WARNING_TEMPLATES = {
    "invalid_numeric_value": "유효하지 않은 수치가 포함된 분석 항목은 설명에서 제외했습니다.",
    "missing_data": "일부 입력 데이터가 없어 유효한 범위만 분석했습니다.",
    "missing_region": "일부 region을 식별할 수 없어 해당 공간 분석을 제외했습니다.",
    "insufficient_field_samples": "일부 region의 유효 sample이 부족해 해당 공간 분석을 제외했습니다.",
    "parameter_extraction_failed": "일부 전기 파라미터를 유효하게 추출하지 못해 관련 비교를 제외했습니다.",
    "non_comparable_visual_scale": "동일한 scale을 사용하지 않아 색상 강도와 고값 영역의 직접 비교를 제한했습니다.",
    "extrapolation": "일부 조건이 학습 범위를 벗어나 결과를 참고 경향으로 해석해야 합니다.",
    "multiple_parameter_change": "여러 device parameter가 함께 달라 개별 parameter의 인과 효과로 단정할 수 없습니다.",
    "conflicting_evidence": "일부 Evidence의 방향이 일치하지 않아 종합적인 개선으로 단정하지 않았습니다.",
    "signed_value_ambiguity": "부호 해석이 불명확하여 magnitude 범위에서만 설명했습니다.",
    "model_approximation": "표시된 결과는 model-derived approximation입니다.",
    "provider_error": "설명 provider를 사용할 수 없어 안전한 로컬 설명으로 전환했습니다.",
    "provider_timeout": "설명 provider 응답 시간이 초과되어 안전한 로컬 설명으로 전환했습니다.",
    "invalid_provider_response": "provider 응답 형식이 유효하지 않아 안전한 로컬 설명으로 전환했습니다.",
}


def make_warning(warning_id: str, warning_type: str, *, severity: str = "medium", fallback_action: str = "return_partial_explanation", **links: Any) -> dict[str, Any]:
    if warning_type not in WARNING_TYPES or severity not in SEVERITIES or fallback_action not in FALLBACK_ACTIONS:
        raise ValueError("Unknown warning enum value.")
    return {"warning_id": warning_id, "warning_type": warning_type, "severity": severity,
            "subject_ids": list(links.get("subject_ids", [])), "comparison_ids": list(links.get("comparison_ids", [])),
            "affected_evidence_ids": list(links.get("affected_evidence_ids", [])), "affected_quantities": list(links.get("affected_quantities", [])),
            "affected_regions": list(links.get("affected_regions", [])), "details": dict(links.get("details", {})),
            "fallback_action": fallback_action, "eligible_for_output": links.get("eligible_for_output", True)}


def render_warning_cautions(warnings: list[dict[str, Any]], limit: int) -> list[str]:
    ranked = sorted((w for w in warnings if w.get("eligible_for_output", True)), key=lambda w: (SEVERITY_ORDER.get(w.get("severity"), 5), w.get("warning_id", "")))
    result = []
    for warning in ranked:
        sentence = WARNING_TEMPLATES.get(warning.get("warning_type"))
        if sentence and sentence not in result: result.append(sentence)
    return result[:max(0, limit)]
