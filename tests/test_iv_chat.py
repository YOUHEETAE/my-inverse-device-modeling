from __future__ import annotations

from backend.explanation.iv_chat import (
    _intent_prompt,
    IVAnalysisSnapshot,
    IVChatService,
    IVQuestionIntent,
    build_iv_context_pack,
)
from backend.explanation.iv_renderer import render_iv_explanation
from backend.explanation.providers.external import ProviderHTTPError
from tests.test_curve_interpretation import curve, payload


def snapshot() -> IVAnalysisSnapshot:
    baseline = curve(
        "Curve 1", length=700, ion=6, ioff=.001, ratio=6000,
        dibl=.10, ss=70, gm=3, ron=3, gds=.1, clm=.05,
    )
    candidate = curve(
        "Curve 2", length=300, ion=16.8, ioff=.1, ratio=250,
        dibl=.46, ss=84, gm=5, ron=1.2, gds=.2, clm=.12,
    )
    baseline["electrical_parameters"]["vth_low_v"]["value"] = .62
    baseline["electrical_parameters"]["vth_high_v"]["value"] = .60
    candidate["electrical_parameters"]["vth_low_v"]["value"] = .50
    candidate["electrical_parameters"]["vth_high_v"]["value"] = .44
    analysis = payload(baseline, candidate).to_dict()
    return IVAnalysisSnapshot(
        analysis_id=analysis["analysis_id"],
        curve_labels=("Curve 1", "Curve 2"),
        payload=analysis,
        automatic_explanation=render_iv_explanation(analysis),
        selection_signature=((0, 1),),
    )


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


def intent(**changes):
    value = {
        "intent": "explain_mechanism",
        "requested_metrics": ["dibl"],
        "requested_mechanisms": ["drain_barrier_coupling_increase"],
        "needs_current_result": True,
        "needs_new_experiment": False,
        "references_previous": False,
        "answer_structure": "cause_and_effect",
    }
    value.update(changes)
    return value


def answer():
    return {
        "answer": (
            "채널 길이가 감소하면 Drain 전위가 Source 쪽 주입 장벽에 "
            "더 강하게 결합합니다. 현재 DIBL 증가는 이 장벽 제어 약화와 "
            "일치하며, Gate가 채널을 단독으로 제어하기 어려워졌다는 뜻입니다."
        ),
        "used_evidence_ids": ["ev_cmp_1_2_dibl"],
        "needs_new_experiment": False,
        "suggested_followup": "이 변화가 Vth와 Ioff에는 어떻게 이어질까요?",
    }


def test_iv_chat_uses_two_stage_grounded_mechanism_pipeline():
    provider = QueueProvider(intent(), answer())
    service = IVChatService(provider)
    result = service.answer(snapshot(), "채널이 짧아질 때 DIBL이 왜 증가해?")
    assert result.source == "external_llm"
    assert result.intent and result.intent.intent == "explain_mechanism"
    assert result.used_evidence_ids == ("ev_cmp_1_2_dibl",)
    assert len(provider.calls) == 2
    answer_request = provider.calls[1][2]
    pack = answer_request["context_pack"]
    assert pack["mechanism_chains"][0]["mechanism_key"] == "drain_barrier_coupling_increase"
    assert pack["current_result_facts"]
    assert len((provider.calls[1][0] + provider.calls[1][1]).encode("utf-8")) < 16_000
    assert "ev_cmp" not in result.answer


def test_iv_chat_rejects_repetitive_answer_with_common_quality_code():
    bad = answer()
    bad["answer"] = "DIBL이 증가했습니다. DIBL이 증가했습니다."
    result = IVChatService(
        QueueProvider(intent(), bad, bad)
    ).answer(snapshot(), "현재 DIBL은 어떻게 변했어?")
    assert result.source == "external_error"
    assert result.diagnostic["repair_trigger"] == (
        "answer_quality_answer_repeats_sentence"
    )
    assert result.diagnostic["message"] == (
        "answer_quality_answer_repeats_sentence"
    )
    record = result.diagnostic["quality_failure"]
    assert record["domain"] == "iv"
    assert record["validation_code"] == (
        "answer_quality_answer_repeats_sentence"
    )
    assert record["replay_payload"] is None


def test_iv_definition_question_excludes_current_result_facts():
    question_intent = IVQuestionIntent(
        intent="define_extraction",
        requested_metrics=("ion",),
        needs_current_result=False,
        answer_structure="definition_and_extraction",
    )
    pack = build_iv_context_pack(snapshot(), question_intent)
    assert pack["current_result_facts"] == []
    assert pack["mechanism_chains"] == []
    assert "ion_ma_per_um" in pack["metric_definitions"]
    assert "Vg=3.0 V" in pack["metric_definitions"]["ion_ma_per_um"]["learning_explanation"]


def test_iv_answer_rate_limit_keeps_intent_checkpoint_for_one_call_retry():
    error = ProviderHTTPError(
        429,
        message="Rate limit reached. Please try again in 2.1s",
        error_type="tokens",
        provider_code="rate_limit_exceeded",
        request_bytes=12_000,
        model="test-model",
        headers={"retry-after": "3"},
    )
    provider = QueueProvider(intent(), error, answer())
    service = IVChatService(provider)
    first = service.answer(snapshot(), "DIBL 증가 이유가 뭐야?")
    assert first.source == "external_error"
    assert first.diagnostic["http_status"] == 429
    assert first.diagnostic["recommended_retry_after_seconds"] == 4
    assert first.intent_checkpoint
    assert "완료된 질문 해석 결과는 보존" in first.answer

    second = service.answer(
        snapshot(),
        "DIBL 증가 이유가 뭐야?",
        intent_checkpoint=first.intent_checkpoint,
    )
    assert second.source == "external_llm"
    assert len(provider.calls) == 3  # two first-turn calls + answer-only retry


def test_iv_hypothetical_intent_requires_new_experiment_flag():
    provider = QueueProvider(
        intent(
            intent="hypothetical",
            needs_new_experiment=False,
            requested_mechanisms=[],
        ),
        intent(
            intent="hypothetical",
            needs_new_experiment=False,
            requested_mechanisms=[],
        ),
    )
    result = IVChatService(provider).answer(
        snapshot(), "채널 길이를 500 nm로 바꾸면 어떻게 돼?"
    )
    assert result.source == "external_error"
    assert result.pipeline_stage == "iv_intent_interpretation_repair"


def test_iv_intent_rate_limit_waits_for_full_token_reset():
    error = ProviderHTTPError(
        429,
        message="Rate limit reached.",
        error_type="tokens",
        provider_code="rate_limit_exceeded",
        request_bytes=3_000,
        model="test-model",
        headers={
            "retry-after": "2",
            "x-ratelimit-reset-tokens": "1m5.2s",
        },
    )
    result = IVChatService(QueueProvider(error)).answer(
        snapshot(), "DIBL 증가 이유가 뭐야?"
    )
    assert result.source == "external_error"
    assert result.diagnostic["recommended_retry_after_seconds"] == 67
    assert not result.intent_checkpoint


def test_iv_chat_answer_carries_model_limitation_caution():
    """The analysis path appends this caution in code, not via the prompt
    (iv_renderer.py), so it is always present. A free-form answer that leans
    on predicted numbers is held to the same standard.
    """
    result = IVChatService(
        QueueProvider(intent(), answer())
    ).answer(snapshot(), "채널이 짧아질 때 DIBL이 왜 증가해?")
    assert result.answer.endswith(
        "이 결과는 학습 모델의 prediction이며 실제 측정 또는 TCAD 검증을 대체하지 않습니다."
    )


def test_iv_chat_definition_answer_has_no_model_caution():
    """A definition says nothing about predicted numbers, so the caution would
    be noise — and noise is how a caveat stops being read.
    """
    define = intent(
        intent="define_extraction",
        needs_current_result=False,
        answer_structure="definition_and_extraction",
        requested_metrics=["ion"],
        requested_mechanisms=[],
    )
    body = answer()
    body["answer"] = (
        "Ion은 지정된 on-state bias 조건에서 측정한 drain 전류를 채널 폭으로 "
        "나눈 값으로 정의하며, 구동 능력을 나타내는 지표로 씁니다."
    )
    body["used_evidence_ids"] = []
    result = IVChatService(QueueProvider(define, body)).answer(snapshot(), "Ion이 뭐야?")
    assert "TCAD 검증을 대체하지 않습니다" not in result.answer


def test_iv_greeting_answers_locally_without_an_answer_call():
    """인사에는 LLM 답변 호출을 쓰지 않는다.

    필요한 건 창의성이 아니라 "여기서 뭘 물을 수 있는지"이고, 그건 화면
    상태를 아는 쪽이 더 정확하다. 매번 같은 문장이 나오는 것도 인사에서는
    흠이 아니며, 토큰과 사용자의 남은 질문 수를 아낀다.
    """
    provider = QueueProvider(intent(
        intent="greeting", needs_current_result=False,
        requested_metrics=[], requested_mechanisms=[], answer_structure="concise",
    ))
    result = IVChatService(provider).answer(snapshot(), "안녕")

    assert result.source == "local_router"
    # 분류 1회뿐 — 답변 생성은 부르지 않는다.
    assert len(provider.calls) == 1
    # 지금 보고 있는 소자를 짚어줘야 안내로 쓸모가 있다.
    assert "Curve 1" in result.answer and "L=700 nm" in result.answer


def test_iv_out_of_scope_answers_locally_with_a_fixed_message():
    provider = QueueProvider(intent(
        intent="out_of_scope", needs_current_result=False,
        requested_metrics=[], requested_mechanisms=[], answer_structure="concise",
    ))
    result = IVChatService(provider).answer(snapshot(), "요즘 페이커 잘하더라")

    assert result.source == "local_router"
    assert len(provider.calls) == 1
    assert "I-V 결과에 대해서만" in result.answer


def test_iv_intent_prompt_defines_out_of_scope_and_greeting():
    """허용값만 나열하고 뜻을 안 적으면 같은 질문이 매번 다르게 분류된다.
    실제로 "안녕"이 어떤 때는 인사로, 어떤 때는 범위 밖으로 갈렸다.
    """
    system, _ = _intent_prompt({"user_question": "안녕"})

    assert "out_of_scope는" in system
    assert "greeting은" in system
