from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from backend.explanation.cross_domain_audit import build_field_iv_audit
from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.field_chat import (
    FieldAnalysisSnapshot,
    FieldChatService,
    FieldQuestionIntent,
    build_field_context_pack,
)
from backend.explanation.field_renderer import render_field_explanation
from backend.explanation.providers.external import ProviderHTTPError
from tests.test_field_interpretation import _predicted_output
from tests.test_field_structured_renderer import _outputs
from tests.test_iv_chat import snapshot as iv_snapshot


class QueueProvider:
    name = "external_llm"
    model = "test-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, system, user, request):
        self.calls.append((system, user, request))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def snapshot() -> FieldAnalysisSnapshot:
    payload = build_field_payload(
        _outputs(), "Electric field", "Auto", "Robust 1-99%"
    ).to_dict()
    return FieldAnalysisSnapshot(
        analysis_id=payload["analysis_id"],
        field_labels=("Curve 1", "Curve 2"),
        display="electric_field",
        payload=payload,
        automatic_explanation=render_field_explanation(payload),
        selection_signature=((0, 1), "Electric field"),
    )


def intent(**changes):
    value = {
        "intent": "explain_physical_meaning",
        "requested_concepts": ["field_concentration"],
        "requested_regions": ["channel_near_surface"],
        "requested_iv_metrics": ["dibl", "vth", "ioff"],
        "needs_current_result": True,
        "needs_new_experiment": False,
        "references_previous": False,
        "answer_structure": "observation_to_iv_check",
    }
    value.update(changes)
    return value


def answer(text: str | None = None):
    evidence_id = snapshot().payload["interpretation"][
        "field_specific_conclusions"
    ][0]["evidence_ids"][0]
    return {
        "answer": text or (
            "현재 채널 표면에서는 국부 전계 집중이 약해지는 공간적 경향이 "
            "보입니다. 이는 Drain 전위가 채널에 결합하는 공간적 영향이 "
            "완화될 가능성과 일치합니다. 다만 Field Map만으로 전기 특성 "
            "변화를 확정할 수 없으므로 I-V 곡선의 DIBL, Vth와 Ioff를 함께 "
            "비교해야 합니다."
        ),
        "used_evidence_ids": [evidence_id],
        "needs_new_experiment": False,
        "suggested_followup": "같은 조건의 I-V 결과에서 어떤 지표부터 볼까요?",
    }


def integrated_snapshot() -> FieldAnalysisSnapshot:
    field_snapshot = snapshot()
    iv_payload = deepcopy(iv_snapshot().payload)
    for iv_subject, field_subject in zip(
        iv_payload["subjects"], field_snapshot.payload["subjects"]
    ):
        iv_subject["display_name"] = field_subject["display_name"]
        iv_subject["device_parameters"] = deepcopy(
            field_subject["device_parameters"]
        )
    return replace(field_snapshot, iv_payload=iv_payload)


def test_field_payload_builds_verification_links_without_electrical_claim() -> None:
    analysis = snapshot().payload
    links = analysis["interpretation"]["cross_domain_links"]
    assert links
    assert all(item["link_status"] == "requires_iv_verification" for item in links)
    assert all(
        item["claim_limit"] == "field_observation_not_electrical_result"
        for item in links
    )
    rendered = render_field_explanation(analysis)
    assert any("I-V" in line and "확정" in line for line in rendered["comparisons"])


def test_field_chat_snapshot_keeps_all_selected_sweep_conditions() -> None:
    outputs = [
        ("Curve 1", _predicted_output(700, 20, 1.0)),
        ("Curve 2", _predicted_output(500, 20, 0.9)),
        ("Curve 3", _predicted_output(350, 20, 0.8)),
    ]
    value = FieldChatService.build_snapshot(
        outputs,
        "Electric field",
        "Auto",
        "Robust 1-99%",
        selection_signature=((0, 1, 2), "Electric field"),
    )
    assert value.field_labels == ("Curve 1", "Curve 2", "Curve 3")
    assert len(value.payload["comparisons"]) == 3
    assert value.payload["comparison_plan"]["analysis_mode"] == (
        "controlled_sweep"
    )
    assert "3개 조건" in " ".join(
        sum(value.automatic_explanation.values(), [])
    )


def test_field_chat_uses_two_stage_grounded_spatial_pipeline() -> None:
    provider = QueueProvider(intent(), answer())
    result = FieldChatService(provider).answer(
        snapshot(), "채널 쪽 전계 변화는 물리적으로 무슨 뜻이야?"
    )
    assert result.source == "external_llm"
    assert result.intent and result.intent.intent == "explain_physical_meaning"
    assert result.used_evidence_ids
    assert len(provider.calls) == 2
    pack = provider.calls[1][2]["context_pack"]
    assert pack["spatial_observations"]
    assert pack["physical_interpretations"]
    assert pack["iv_verification_links"]
    assert len((provider.calls[1][0] + provider.calls[1][1]).encode("utf-8")) < 14_000
    assert "ev_cmp" not in result.answer


def test_field_chat_rejects_repetitive_answer_with_common_quality_code() -> None:
    bad = answer("전계가 집중됩니다. 전계가 집중됩니다.")
    result = FieldChatService(
        QueueProvider(intent(), bad, bad)
    ).answer(snapshot(), "현재 채널 전계는 어떻게 보여?")
    assert result.source == "external_error"
    assert result.diagnostic["repair_trigger"] == (
        "answer_quality_answer_repeats_sentence"
    )
    assert result.diagnostic["message"] == (
        "answer_quality_answer_repeats_sentence"
    )
    assert result.diagnostic["quality_failure"]["domain"] == "field"


def test_field_intent_accepts_extra_metadata_and_omitted_empty_fields() -> None:
    provider = QueueProvider(
        {
            "intent": "explain_overall",
            "needs_current_result": True,
            "confidence": 0.96,
        },
        answer(
            "Field Map에서는 먼저 표시 물리량과 색상 범위를 확인하고, "
            "채널 표면과 Source/Drain 인접 영역의 분포 및 국부 집중을 "
            "비교해야 합니다. 그 공간적 관찰이 어떤 소자 물리와 "
            "일치하는지 해석한 뒤 I-V 지표에서 별도로 확인해야 합니다."
        ),
    )
    result = FieldChatService(provider).answer(
        snapshot(), "fieldmap에서는 뭐를 보면 되는거야?"
    )
    assert result.source == "external_llm"
    assert result.intent
    assert result.intent.intent == "explain_overall"
    assert result.intent.answer_structure == "overview"
    assert result.intent.requested_concepts == ()
    assert result.intent.requested_regions == ()
    assert result.intent.requested_iv_metrics == ()
    assert len(provider.calls) == 2
    intent_request = provider.calls[0][2]
    assert "explain_overall" in intent_request["allowed_intents"]
    assert "overview" in intent_request["allowed_answer_structures"]
    assert intent_request["response_keys"] == [
        "intent", "requested_concepts", "requested_regions",
        "requested_iv_metrics", "needs_current_result",
        "needs_new_experiment", "references_previous",
        "answer_structure",
    ]


def test_field_quantification_question_uses_one_grounded_answer_call() -> None:
    current = snapshot()
    selected_ids = [
        item["evidence_id"]
        for item in current.payload["evidence"]
        if item.get("selected_for_explanation")
    ]
    response = {
        "answer": (
            "1. 입력 조건에서는 Channel length와 Oxide thickness의 변경값을 "
            "구분해 봅니다.\n"
            "2. Field 분포는 영역별 p99 수준, hotspot의 p99 강도, 공통 p90 "
            "기준 이상 면적 비율, hotspot 위치 이동으로 수치화합니다. 현재 "
            "선택된 공간 관찰에서는 채널 표면 hotspot이 약해지고 전체 hotspot "
            "위치는 오른쪽으로 이동했습니다. 다만 현재 Field raw value는 표시 "
            "허용 대상이 아니므로 검증된 변화 방향만 말할 수 있습니다. 또한 "
            "Electric field만으로 breakdown 발생을 확정할 수 없습니다."
        ),
        "used_evidence_ids": selected_ids,
        "needs_new_experiment": False,
        "suggested_followup": None,
    }
    provider = QueueProvider(response)
    result = FieldChatService(provider).answer(
        current,
        "그럼 fieldmap에서는 어떤 파라미터 값으로 변화를 수치화하고 "
        "현재 상황에서 변화하는 파라미터는 뭐가 있어?",
    )
    assert result.source == "external_llm"
    assert result.intent and result.intent.intent == "compare_maps"
    assert len(provider.calls) == 1
    pack = provider.calls[0][2]["context_pack"]
    assert pack["quantification_guide"]["method_catalog"]
    assert pack["quantification_guide"]["current_spatial_changes"]
    assert all(
        not item["numeric_values_allowed"]
        for item in pack["quantification_guide"]["current_spatial_changes"]
    )
    assert "baseline_internal_value" not in provider.calls[0][1]
    assert "candidate_internal_value" not in provider.calls[0][1]


def test_field_quantification_still_rejects_positive_breakdown_claim() -> None:
    bad = answer(
        "현재 Field에서는 채널의 hotspot 변화를 볼 수 있으며, "
        "breakdown 발생이 확인되었습니다."
    )
    result = FieldChatService(QueueProvider(bad, bad)).answer(
        snapshot(),
        "fieldmap 변화를 어떤 값으로 수치화해?",
    )
    assert result.source == "external_error"
    assert result.diagnostic["repair_trigger"] == (
        "field_answer_claims_unverified_breakdown"
    )


def test_field_answer_rejects_unverified_electrical_result_claim() -> None:
    bad = answer("현재 Field에서 DIBL 증가가 확인되었습니다.")
    provider = QueueProvider(intent(), bad, bad)
    result = FieldChatService(provider).answer(
        snapshot(), "이 Field에서 DIBL 증가가 확인된 거야?"
    )
    assert result.source == "external_error"
    assert result.pipeline_stage == "field_answer_generation_repair"
    assert result.diagnostic["repair_trigger"] == (
        "field_answer_claims_unverified_electrical_change"
    )


def test_field_theory_question_can_exclude_current_spatial_result() -> None:
    question_intent = FieldQuestionIntent(
        intent="define_display",
        needs_current_result=False,
        answer_structure="definition",
    )
    pack = build_field_context_pack(snapshot(), question_intent)
    assert pack["spatial_observations"] == []
    assert pack["physical_interpretations"] == []
    assert pack["iv_verification_links"] == []
    assert pack["theory_facts"]


def test_cross_domain_audit_keeps_field_and_iv_evidence_separate() -> None:
    combined = integrated_snapshot()
    audit = build_field_iv_audit(
        combined.payload, combined.iv_payload, requested_metrics={"dibl", "vth"}
    )
    assert audit["status"] == "verified_iv_evidence_available"
    assert audit["subject_alignment"] == "exact"
    assert {item["quantity"] for item in audit["verified_iv_facts"]} == {
        "dibl", "vth_at_vd_0_05", "vth_at_vd_1_5",
    }
    assert all(
        item["source_domain"] == "iv_curve"
        for item in audit["verified_iv_facts"]
    )
    assert "caused" not in audit


def test_field_chat_can_report_separately_verified_iv_direction() -> None:
    combined = integrated_snapshot()
    field_evidence = combined.payload["interpretation"][
        "field_specific_conclusions"
    ][0]["evidence_ids"][0]
    provider = QueueProvider(
        intent(requested_iv_metrics=["dibl"]),
        {
            "answer": (
                "현재 Field에서는 채널 표면의 전계 집중이 약해지는 공간적 "
                "경향이 보입니다. 별도로 같은 소자의 I-V 결과에서는 DIBL "
                "증가가 확인되었습니다. 두 관찰은 함께 해석할 수 있지만, "
                "Field 변화가 DIBL 변화를 일으켰다고 단정할 수는 없습니다."
            ),
            "used_evidence_ids": [field_evidence, "ev_cmp_1_2_dibl"],
            "needs_new_experiment": False,
            "suggested_followup": None,
        },
    )
    result = FieldChatService(provider).answer(
        combined, "Field 변화와 실제 DIBL 결과를 같이 설명해줘."
    )
    assert result.source == "external_llm"
    assert "ev_cmp" not in result.answer
    assert set(result.used_evidence_ids) == {
        field_evidence, "ev_cmp_1_2_dibl",
    }
    assert len(
        (provider.calls[1][0] + provider.calls[1][1]).encode("utf-8")
    ) < 14_000


def test_field_chat_rejects_direction_conflicting_with_verified_iv() -> None:
    combined = integrated_snapshot()
    field_evidence = combined.payload["interpretation"][
        "field_specific_conclusions"
    ][0]["evidence_ids"][0]
    bad = {
        "answer": (
            "현재 Field 관찰과 함께 I-V 결과에서는 DIBL 감소가 "
            "확인되었습니다."
        ),
        "used_evidence_ids": [field_evidence, "ev_cmp_1_2_dibl"],
        "needs_new_experiment": False,
        "suggested_followup": None,
    }
    result = FieldChatService(
        QueueProvider(intent(requested_iv_metrics=["dibl"]), bad, bad)
    ).answer(combined, "Field와 DIBL 결과를 함께 설명해줘.")
    assert result.source == "external_error"
    assert result.diagnostic["repair_trigger"] == (
        "field_answer_claims_unverified_electrical_change"
    )


def test_field_answer_rate_limit_keeps_intent_checkpoint() -> None:
    error = ProviderHTTPError(
        429,
        message="Rate limit reached. Please try again in 2s",
        error_type="tokens",
        provider_code="rate_limit_exceeded",
        request_bytes=9_000,
        model="test-model",
        headers={"retry-after": "2"},
    )
    provider = QueueProvider(intent(), error, answer())
    service = FieldChatService(provider)
    first = service.answer(snapshot(), "채널 전계 변화가 무슨 뜻이야?")
    assert first.source == "external_error"
    assert first.intent_checkpoint
    assert first.diagnostic["recommended_retry_after_seconds"] == 3
    second = service.answer(
        snapshot(),
        "채널 전계 변화가 무슨 뜻이야?",
        intent_checkpoint=first.intent_checkpoint,
    )
    assert second.source == "external_llm"
    assert len(provider.calls) == 3
