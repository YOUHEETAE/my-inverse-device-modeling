from __future__ import annotations

from backend.explanation.comparison_focus import (
    compact_context_comparisons,
    compact_device_conditions,
    focus_allows_item,
    resolve_comparison_focus,
    validate_focused_claim_text,
)
from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.field_chat import (
    FieldAnalysisSnapshot,
    FieldQuestionIntent,
    build_field_context_pack,
)
from backend.explanation.field_renderer import render_field_explanation
from backend.explanation.iv_chat import (
    IVAnalysisSnapshot,
    IVChatService,
    IVQuestionIntent,
    build_iv_context_pack,
)
from backend.explanation.iv_renderer import render_iv_explanation
from tests.test_curve_interpretation import curve, payload_many
from tests.test_field_interpretation import _predicted_output


def _iv_sweep_payload():
    return payload_many([
        curve("Curve 1", length=700, ion=7, ioff=.001),
        curve("Curve 2", length=500, ion=9, ioff=.01),
        curve("Curve 3", length=300, ion=13, ioff=.1),
    ]).to_dict()


def _iv_snapshot() -> IVAnalysisSnapshot:
    payload = _iv_sweep_payload()
    return IVAnalysisSnapshot(
        analysis_id=payload["analysis_id"],
        curve_labels=("Curve 1", "Curve 2", "Curve 3"),
        payload=payload,
        automatic_explanation=render_iv_explanation(payload),
    )


def _field_snapshot() -> FieldAnalysisSnapshot:
    payload = build_field_payload(
        [
            ("Curve 1", _predicted_output(700, 20, 1.0)),
            ("Curve 2", _predicted_output(500, 20, 0.9)),
            ("Curve 3", _predicted_output(300, 20, 0.8)),
        ],
        "Electric field",
        "Auto",
        "Robust 1-99%",
    ).to_dict()
    return FieldAnalysisSnapshot(
        analysis_id=payload["analysis_id"],
        field_labels=("Curve 1", "Curve 2", "Curve 3"),
        display="electric_field",
        payload=payload,
        automatic_explanation=render_field_explanation(payload),
    )


def test_numeric_conditions_resolve_to_existing_pair() -> None:
    payload = _iv_sweep_payload()
    focus = resolve_comparison_focus(
        payload, "500 nm와 300 nm만 비교해줘."
    )
    assert focus.focus_mode == "specific_pair"
    assert focus.subject_ids == ("curve_2", "curve_3")
    assert focus.comparison_ids == ("cmp_2_3",)
    assert focus.plan_analysis_mode == "controlled_sweep"
    assert focus.original_plan_claim_level == "controlled_association"
    abbreviated = resolve_comparison_focus(
        payload, "Curve 2와 3만 비교해줘."
    )
    assert abbreviated.comparison_ids == ("cmp_2_3",)


def test_full_sweep_and_ambiguous_pair_are_distinguished() -> None:
    payload = _iv_sweep_payload()
    full = resolve_comparison_focus(payload, "전체 L sweep 추세를 설명해줘.")
    assert full.focus_mode == "full_plan"
    assert len(full.comparison_ids) == 3

    ambiguous = resolve_comparison_focus(payload, "두 곡선을 비교해줘.")
    assert ambiguous.focus_mode == "clarification"
    assert ambiguous.requires_clarification
    assert ambiguous.clarification_reason == "comparison_targets_ambiguous"


def test_followup_inherits_previous_pair_focus() -> None:
    payload = _iv_sweep_payload()
    previous = resolve_comparison_focus(
        payload, "Curve 2와 Curve 3만 비교해줘."
    )
    current = resolve_comparison_focus(
        payload,
        "그 둘 중에서는 SS가 왜 달라?",
        history=[{"comparison_focus": previous.to_dict()}],
    )
    assert current.focus_mode == "specific_pair"
    assert current.comparison_ids == ("cmp_2_3",)
    assert current.source == "previous_turn"


def test_nonconsecutive_display_labels_do_not_alias_internal_subject_order() -> None:
    payload = _iv_sweep_payload()
    payload["subjects"][1]["display_name"] = "Curve 4"
    focus = resolve_comparison_focus(
        payload, "Curve 1과 Curve 4를 비교해줘."
    )
    assert focus.subject_ids == ("curve_1", "curve_2")
    assert focus.comparison_ids == ("cmp_1_2",)


def test_iv_context_pack_contains_only_focused_pair_evidence() -> None:
    snapshot = _iv_snapshot()
    focus = resolve_comparison_focus(
        snapshot.payload, "500과 300만 비교해줘."
    )
    pack = build_iv_context_pack(
        snapshot,
        IVQuestionIntent(
            intent="compare_curves",
            requested_metrics=("ion", "ioff"),
            answer_structure="comparison",
        ),
        focus,
    )
    assert len(pack["comparisons"]) == 1
    assert pack["comparisons"][0]["baseline"] == "Curve 2"
    assert pack["comparisons"][0]["candidate"] == "Curve 3"
    assert all(
        "cmp_1_" not in evidence_id
        for evidence_id in pack["allowed_evidence_ids"]
    )
    assert all(
        focus_allows_item(item, focus)
        for item in snapshot.payload["evidence"]
        if item.get("evidence_id") in pack["allowed_evidence_ids"]
    )
    assert pack["comparison_focus"]["focused_claim_level"] == (
        "controlled_association"
    )


def test_full_sweep_context_factors_fixed_parameters_and_avoids_all_pairs() -> None:
    snapshot = _iv_snapshot()
    focus = resolve_comparison_focus(
        snapshot.payload, "전체 sweep 추세를 설명해줘."
    )
    comparisons = compact_context_comparisons(snapshot.payload, focus)
    devices, fixed = compact_device_conditions(snapshot.payload, focus)
    assert len(comparisons) == 2
    assert fixed
    assert all(
        set(item["varied_parameters"]) == {"channel_length_nm"}
        for item in devices
    )


def test_field_context_re_ranks_the_requested_nonrepresentative_pair() -> None:
    snapshot = _field_snapshot()
    # The displayed sweep endpoints are Curve 3 and Curve 1. Ask for the
    # intermediate pair to prove that chat does not borrow endpoint evidence.
    focus = resolve_comparison_focus(
        snapshot.payload, "Curve 2와 Curve 3만 비교해줘."
    )
    pack = build_field_context_pack(
        snapshot,
        FieldQuestionIntent(
            intent="compare_maps",
            needs_current_result=True,
            answer_structure="comparison",
        ),
        focus,
    )
    assert len(pack["comparisons"]) == 1
    assert pack["spatial_observations"]
    assert pack["physical_interpretations"]
    assert all(
        "cmp_2_3" in evidence_id
        for evidence_id in pack["allowed_evidence_ids"]
    )
    assert pack["multi_condition_trends"] == []

    full_pack = build_field_context_pack(
        snapshot,
        FieldQuestionIntent(
            intent="compare_maps",
            needs_current_result=True,
            answer_structure="comparison",
        ),
        resolve_comparison_focus(
            snapshot.payload, "전체 sweep 추세를 설명해줘."
        ),
    )
    assert full_pack["multi_condition_trends"]
    assert all(
        "internal_values" not in item
        and item["numeric_values_allowed"] is False
        for item in full_pack["multi_condition_trends"]
    )


class _CountingProvider:
    name = "external_llm"
    model = "unused"

    def __init__(self):
        self.calls = 0

    def generate(self, _system, _user, _request):
        self.calls += 1
        raise AssertionError("ambiguous focus must not call provider")


class _IVFocusProvider:
    name = "external_llm"
    model = "focus-test"

    def __init__(self):
        self.calls = []

    def generate(self, _system, _user, request):
        self.calls.append(request)
        if "context_pack" not in request:
            return {
                "intent": "compare_curves",
                "requested_metrics": ["ion"],
                "requested_mechanisms": [],
                "needs_current_result": True,
                "needs_new_experiment": False,
                "references_previous": False,
                "answer_structure": "comparison",
            }
        evidence_id = next(
            item
            for item in request["context_pack"]["allowed_evidence_ids"]
            if "cmp_2_3" in item and item.endswith("_ion")
        )
        return {
            "answer": (
                "Curve 2 대비 Curve 3의 Ion 변화를 해당 두 조건의 "
                "추출 결과로 비교할 수 있습니다. 이 초점은 전체 sweep을 "
                "새 분석으로 바꾼 것이 아니라 기존 pair 근거만 좁힌 것입니다."
            ),
            "used_evidence_ids": [evidence_id],
            "needs_new_experiment": False,
            "suggested_followup": (
                "같은 두 조건에서 Ioff도 함께 비교해 볼까요?"
            ),
        }


def test_ambiguous_iv_comparison_returns_local_clarification_without_api() -> None:
    provider = _CountingProvider()
    result = IVChatService(provider).answer(
        _iv_snapshot(), "두 곡선을 비교해줘."
    )
    assert result.source == "local_router"
    assert result.intent and result.intent.intent == "clarify"
    assert "비교 대상을 지정" in result.answer
    assert provider.calls == 0


def test_iv_service_passes_only_resolved_pair_to_answer_generation() -> None:
    provider = _IVFocusProvider()
    result = IVChatService(provider).answer(
        _iv_snapshot(), "500 nm와 300 nm의 Ion만 비교해줘."
    )
    assert result.source == "external_llm"
    assert len(provider.calls) == 2
    pack = provider.calls[1]["context_pack"]
    assert len(pack["comparisons"]) == 1
    assert tuple(pack["comparison_focus"]["comparison_ids"]) == ("cmp_2_3",)
    assert all(
        "cmp_1_" not in evidence_id
        for evidence_id in pack["allowed_evidence_ids"]
    )
    assert result.diagnostic["comparison_focus"]["focus_mode"] == (
        "specific_pair"
    )


def test_compound_focus_rejects_promoted_single_parameter_causality() -> None:
    pack = {
        "comparisons": [{
            "changed_parameters": [
                {"parameter": "channel_length"},
                {"parameter": "oxide_thickness"},
            ],
        }],
    }
    try:
        validate_focused_claim_text(
            "Channel length 감소로 인해 Ion이 증가했습니다.",
            pack,
            error_code="claim_promoted",
        )
    except ValueError as error:
        assert str(error) == "claim_promoted"
    else:
        raise AssertionError("promoted compound causality was accepted")

    validate_focused_claim_text(
        "일반적으로 Channel length 감소는 Ion 증가 가능성과 연결되지만 "
        "Tox도 함께 변해 개별 기여를 분리할 수 없습니다.",
        pack,
        error_code="claim_promoted",
    )
