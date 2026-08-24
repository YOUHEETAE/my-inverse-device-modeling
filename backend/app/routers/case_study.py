"""Case Study learning endpoints.

These expose the learning pipeline the desktop app drives directly
(frontend/visualization/case_study/panel.py). The step order, the save
points, and the state transitions are taken from there rather than
reinvented — a session that moves differently here would produce progress
records the desktop app cannot read, and both read the same TopicConfig.

Sessions are not stored here. The desktop app keeps them in local JSON
files (JsonSessionRepository) because it has no accounts; the web keeps them
in Postgres keyed by the logged-in user, which lives in java_service. So each
endpoint takes the session in and returns the updated one, leaving Python
stateless — the same split the free-form chat endpoints use.

The split into separate submit/run endpoints mirrors the desktop app's save
points exactly. panel.py saves after submit_predictions and *then* starts the
simulation, so a failed experiment leaves a saved session at
PREDICTION_SUBMITTED that can be retried (_arm_case_retry_button); the same
holds for submit_observations followed by evaluation (_resume_evaluation).
Collapsing either pair into one call would lose the answers on failure.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import learning_runner, learning_state_machine, learning_tutor
from backend.learning.llm_service import LearningLLMService
from backend.learning.case_presentation import (
    CASE_CORE_SUMMARIES,
    CASE_UNDERSTANDING_GUIDES,
    CONCEPT_FEEDBACK_LABELS,
    CONDITION_LABELS,
    MODEL_ANSWER_SECTION_TITLES,
    QUESTION_REVIEW_GUIDES,
    format_case_comparison,
)
from backend.learning.progress import build_learning_portfolio
from backend.learning.schemas import LearningSession, LearningStep
from backend.learning.state_machine import InvalidLearningTransition
from backend.learning.topics import TopicConfigError, load_topics
from backend.learning.workflow import apply_observation_review, review_observations

router = APIRouter()


class TopicSummary(BaseModel):
    topic_id: str
    title: str
    description: str
    catalog_order: int
    prerequisite_topic_ids: list[str]
    # 카드의 "변경 조건" 한 줄. 케이스마다 규칙이 다르다 — 단일 파라미터
    # 비교는 값과 단위를 조합하고(Channel length: 700 nm → 300 nm), 2x2나
    # 후보군 비교는 케이스가 지정한 문구를 쓴다. 데스크톱 앱과 같은 함수로
    # 만들어야 두 화면의 문구가 갈라지지 않는다.
    comparison_caption: str
    changed_parameters: list[str]
    # 화면에 쓰는 이름 ("L" -> "Channel length")
    parameter_labels: dict[str, str]
    baseline_label: str
    comparison_label: str


class SafeQuestion(BaseModel):
    question_id: str
    type: str
    prompt: str
    options: list[str]
    reason_required: bool
    # 완료 화면에서 이 질문을 되짚을 때 쓰는 제목과, 함께 보여줄 지표.
    # 정답은 여전히 빠져 있다.
    review_title: str = ""
    review_metrics: list[str] = Field(default_factory=list)


class ReferenceCondition(BaseModel):
    condition_id: str
    label: str
    conditions: dict[str, float]


class CaseGuide(BaseModel):
    """"1. Case 이해" 화면의 내용."""

    context: str
    question: str
    evidence: list[str]
    caution: str


class TopicDetail(TopicSummary):
    learning_objectives: list[str]
    baseline_conditions: dict[str, float]
    comparison_conditions: dict[str, float]
    condition_descriptions: dict[str, str]
    theory_concepts: list[str]
    theory_reference: str
    # 'controlled_pair' | 'two_by_two' | 'candidate_set'
    comparison_design: str
    # 2x2나 후보군 비교에서 baseline/comparison 말고 함께 보여줄 조건들
    reference_conditions: list[ReferenceCondition]
    # 조건 표에 실제로 띄울 파라미터. 비어 있으면 전부 보여준다.
    display_parameters: list[str]
    guide: CaseGuide
    # 완료 화면의 "핵심 정리".
    core_summary: list[str]
    # 개념 id를 사람이 읽는 말로 (summary_snapshot의 understood_concepts와
    # detected_misconceptions가 id로 오기 때문에 필요하다).
    concept_labels: dict[str, str]
    # 모범 답안을 섹션으로 나눌 때 쓰는 제목.
    model_answer_sections: dict[str, str]
    prediction_questions: list[SafeQuestion]
    observation_questions: list[SafeQuestion]


class SessionRequest(BaseModel):
    """Java가 보관하던 세션을 그대로 돌려준다."""

    session: dict[str, Any]


class AnswerRequest(SessionRequest):
    # question_id -> 학습자 답변. 상태머신이 형식을 검증한다.
    answers: dict[str, Any]


class FollowupRequest(SessionRequest):
    question: str = Field(min_length=1, max_length=800)


class NewSessionRequest(BaseModel):
    topic_id: str


class PortfolioRequest(BaseModel):
    """내 학습 현황. 세션 목록만으로 계산되는 순수 함수라 상태가 필요없다."""

    sessions: list[dict[str, Any]] = Field(default_factory=list)


class CurveData(BaseModel):
    kind: str
    grid: list[float]
    fixed_biases: list[float]
    currents: list[list[float]]


class ConditionRunView(BaseModel):
    """한 조건의 I-V 곡선.

    Field Map은 담지 않는다. 조건이 곧 소자 파라미터(L/T/B/SD/LDD)라
    화면이 기존 /fields/predict와 /fields/display를 그대로 부르면 되고,
    같은 입력이면 같은 결과가 나온다. 여기에 실으면 응답이 3 MB를 넘는데,
    그중 대부분은 화면이 어느 표시를 고를지도 모르는 상태의 원자료다.
    """

    label: str
    # 그대로 /fields/predict에 넘길 수 있는 값
    conditions: dict[str, float]
    idvd: CurveData
    idvg: CurveData


class ExperimentResult(BaseModel):
    """화면에 그릴 실행 결과.

    세션에 담지 않는다. 곡선과 Field Map을 다 넣으면 세션이 수백 KB가 되는데,
    걸음마다 자바와 Python 사이를 왕복하는 구조라 매 단계가 무거워진다.
    데스크톱 앱도 이 결과를 메모리에만 두고, 저장된 세션을 다시 열면
    "그래프 다시 생성"으로 다시 만든다 (panel.py의 _build_curve_view).
    """

    # 표시 순서대로. 2x2나 후보군 비교면 baseline/comparison 앞에
    # reference 조건들이 붙는다.
    runs: list[ConditionRunView]


class SessionResponse(BaseModel):
    session: dict[str, Any]


class ExperimentResponse(SessionResponse):
    result: ExperimentResult


class FollowupResponsePayload(SessionResponse):
    answer: str
    source: str


def _topics() -> dict:
    try:
        return load_topics()
    except TopicConfigError as error:
        raise HTTPException(status_code=500, detail=f"invalid_topic_config:{error}") from error


def _topic_or_404(topic_id: str):
    topics = _topics()
    if topic_id not in topics:
        raise HTTPException(status_code=404, detail="unknown_learning_topic")
    return topics[topic_id]


def _load_session(payload: dict[str, Any]) -> LearningSession:
    try:
        return LearningSession.from_dict(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="invalid_learning_session") from error


def _session_topic(session: LearningSession):
    if not session.topic_id:
        raise HTTPException(status_code=400, detail="session_has_no_topic")
    return _topic_or_404(session.topic_id)


def _safe_question(question) -> SafeQuestion:
    # 정답(correct_options)과 개념 매핑은 내보내지 않는다 — 학습자가 예측을
    # 적기 전에 답을 볼 수 있으면 예측 단계 자체가 의미를 잃는다.
    guide = QUESTION_REVIEW_GUIDES.get(question.question_id, {})
    return SafeQuestion(
        question_id=question.question_id,
        type=question.type,
        prompt=question.prompt,
        options=list(question.options),
        reason_required=question.reason_required,
        review_title=str(guide.get("title", "")),
        review_metrics=list(guide.get("metric_keys", ())),
    )


def _summary(topic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "title": topic.title,
        "description": topic.description,
        "catalog_order": topic.catalog_order,
        "prerequisite_topic_ids": list(topic.prerequisite_topic_ids),
        # 데스크톱 카드는 "전기적 파라미터 (...)" 껍데기를 벗겨서 쓴다.
        "comparison_caption": (
            format_case_comparison(topic)[0]
            .removeprefix("전기적 파라미터 (")
            .removesuffix(")")
        ),
        "changed_parameters": list(
            compare_conditions(topic.baseline_conditions, topic.comparison_conditions)
        ),
        "parameter_labels": dict(CONDITION_LABELS),
        "baseline_label": topic.baseline_label,
        "comparison_label": topic.comparison_label,
    }


def compare_conditions(baseline: dict[str, float], comparison: dict[str, float]) -> tuple[str, ...]:
    return tuple(key for key in baseline if baseline.get(key) != comparison.get(key))


def _guide(topic) -> CaseGuide:
    # 데스크톱 앱과 같은 폴백 (panel.py의 _build_introduction).
    value = CASE_UNDERSTANDING_GUIDES.get(
        topic.topic_id,
        {
            "context": topic.description,
            "question": topic.prediction_questions[0].prompt,
            "evidence": tuple(topic.required_outputs),
            "caution": "한 가지 결과만으로 원인을 단정하지 않습니다.",
        },
    )
    return CaseGuide(
        context=value["context"],
        question=value["question"],
        evidence=list(value["evidence"]),
        caution=value["caution"],
    )


@router.get("/case-study/topics")
def list_case_study_topics() -> list[TopicSummary]:
    return [TopicSummary(**_summary(topic)) for topic in _topics().values()]


@router.get("/case-study/topics/{topic_id}")
def get_case_study_topic(topic_id: str) -> TopicDetail:
    topic = _topic_or_404(topic_id)
    return TopicDetail(
        **_summary(topic),
        learning_objectives=list(topic.learning_objectives),
        baseline_conditions=dict(topic.baseline_conditions),
        comparison_conditions=dict(topic.comparison_conditions),
        condition_descriptions=dict(topic.condition_descriptions),
        theory_concepts=list(topic.theory_concepts),
        theory_reference=topic.theory_reference,
        comparison_design=topic.comparison_design,
        reference_conditions=[
            ReferenceCondition(
                condition_id=item.condition_id, label=item.label, conditions=dict(item.conditions))
            for item in topic.reference_conditions
        ],
        display_parameters=list(topic.display_parameters),
        guide=_guide(topic),
        core_summary=list(CASE_CORE_SUMMARIES.get(topic.topic_id, ())),
        # 이 케이스에 등장하는 개념만 추린다 — 100개를 다 보낼 이유가 없다.
        concept_labels={
            name: CONCEPT_FEEDBACK_LABELS[name]
            for name in (*topic.expected_concepts, *topic.common_misconceptions)
            if name in CONCEPT_FEEDBACK_LABELS
        },
        model_answer_sections=dict(MODEL_ANSWER_SECTION_TITLES),
        prediction_questions=[_safe_question(item) for item in topic.prediction_questions],
        observation_questions=[_safe_question(item) for item in topic.observation_questions],
    )


# 내 학습 현황. 진도·다음 추천 케이스·선행 조건 충족 여부가 모두 여기서 나온다.
@router.post("/case-study/portfolio")
def case_study_portfolio(request: PortfolioRequest) -> dict[str, Any]:
    sessions = [_load_session(item) for item in request.sessions]
    return build_learning_portfolio(_topics(), sessions).to_dict()


@router.post("/case-study/sessions")
def create_case_study_session(request: NewSessionRequest) -> SessionResponse:
    session = LearningSession.create(_topic_or_404(request.topic_id))
    return SessionResponse(session=session.to_dict())


# 현재 세션을 처음 단계로 되돌린다. panel.py의 _reset_current_session과 같이
# session_id / display_name / ui_state는 남긴다 — 목록에서 같은 기록으로
# 보여야 하고, 사용자가 붙인 이름도 유지돼야 한다.
@router.post("/case-study/sessions/reset")
def reset_case_study_session(request: SessionRequest) -> SessionResponse:
    session = _load_session(request.session)
    replacement = LearningSession.create(_session_topic(session))
    replacement.session_id = session.session_id
    replacement.display_name = session.display_name
    replacement.ui_state = dict(session.ui_state)
    return SessionResponse(session=replacement.to_dict())


# 실험이나 평가가 실패하면 세션이 ERROR로 남는다. 되돌릴 방법이 없으면
# 학습자는 답변을 다 적어두고도 그 세션을 버려야 한다
# (panel.py의 _retry_error -> state_machine.recover).
#
# 복구 후 어느 단계로 돌아가는지는 응답의 current_step에 담겨 나가고,
# SIMULATION_RUNNING이면 experiment를, OBSERVATION_SUBMITTED면 evaluation을
# 다시 부르면 된다.
@router.post("/case-study/sessions/recover")
def recover_session(request: SessionRequest) -> SessionResponse:
    session = _load_session(request.session)
    try:
        learning_state_machine.recover(session)
    except InvalidLearningTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SessionResponse(session=session.to_dict())


# "사전 예측 시작". INTRODUCTION -> BASELINE_SETUP -> PREDICTION_QUESTION을
# 한 번에 밟는다 (panel.py의 _begin_prediction).
@router.post("/case-study/sessions/begin-prediction")
def begin_prediction(request: SessionRequest) -> SessionResponse:
    session = _load_session(request.session)
    try:
        if session.current_step is LearningStep.INTRODUCTION:
            learning_state_machine.transition(session, LearningStep.BASELINE_SETUP)
        learning_state_machine.transition(session, LearningStep.PREDICTION_QUESTION)
    except InvalidLearningTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SessionResponse(session=session.to_dict())


@router.post("/case-study/sessions/predictions")
def submit_predictions(request: AnswerRequest) -> SessionResponse:
    session = _load_session(request.session)
    try:
        learning_state_machine.submit_predictions(session, request.answers)
    except InvalidLearningTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SessionResponse(session=session.to_dict())


# 모델 추론이 도는 단계라 느리다. 예측 제출과 나눠둔 덕분에 여기서 실패해도
# 학습자의 답변은 이미 저장되어 있고, 같은 세션으로 다시 부르면 된다.
def _curve(value) -> CurveData:
    return CurveData(
        kind=value.kind,
        grid=value.grid.tolist(),
        fixed_biases=value.fixed_biases.tolist(),
        currents=value.currents.tolist(),
    )


def _runs(result) -> ExperimentResult:
    # 데스크톱과 같은 순서 (LearningExperimentResult.display_runs):
    # reference들 뒤에 baseline, comparison.
    return ExperimentResult(
        runs=[
            ConditionRunView(
                label=run.label,
                conditions=dict(run.conditions),
                idvd=_curve(run.idvd),
                idvg=_curve(run.idvg),
            )
            for run in result.display_runs
        ]
    )


# 저장된 세션을 다시 열었을 때 그래프만 되살린다. 세션 상태는 건드리지
# 않는다 — 데스크톱의 "그래프 다시 생성"과 같다
# (panel.py의 _start_simulation(use_session_transition=False)).
@router.post("/case-study/sessions/regenerate")
def regenerate_experiment(request: SessionRequest) -> ExperimentResult:
    session = _load_session(request.session)
    try:
        return _runs(learning_runner.execute(_session_topic(session)))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="learning_experiment_failed") from error


@router.post("/case-study/sessions/experiment")
def run_experiment(request: SessionRequest) -> ExperimentResponse:
    session = _load_session(request.session)
    topic = _session_topic(session)
    try:
        result = learning_runner.execute_for_session(session, topic, learning_state_machine)
        session.analysis_snapshot = result.learning_context.to_dict()
        # panel.py는 RESULT_READY에서 멈추지 않고 관찰 질문까지 밀어둔다.
        if session.current_step is LearningStep.SIMULATION_RUNNING:
            learning_state_machine.transition(session, LearningStep.RESULT_READY)
        if session.current_step is LearningStep.RESULT_READY:
            learning_state_machine.transition(session, LearningStep.OBSERVATION_QUESTION)
    except InvalidLearningTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001 - 실행 실패를 학습자에게 알려야 한다
        raise HTTPException(status_code=502, detail="learning_experiment_failed") from error
    return ExperimentResponse(session=session.to_dict(), result=_runs(result))


@router.post("/case-study/sessions/observations")
def submit_observations(request: AnswerRequest) -> SessionResponse:
    session = _load_session(request.session)
    try:
        learning_state_machine.submit_observations(session, request.answers)
    except InvalidLearningTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SessionResponse(session=session.to_dict())


def _latest_answers(records, question_ids: set[str]) -> dict[str, Any]:
    """같은 질문을 다시 답했으면 마지막 답을 쓴다 (panel.py의 _latest_*_answers)."""
    answers: dict[str, Any] = {}
    for record in reversed(records):
        if record.question_id in question_ids and record.question_id not in answers:
            answers[record.question_id] = record.raw_answer
    return answers


# LLM 채점과 맞춤 피드백. 실패하면 세션을 ERROR로 표시해 돌려주므로
# (panel.py의 fail_evaluation) 프론트가 재시도 버튼을 띄울 수 있다.
@router.post("/case-study/sessions/evaluation")
def evaluate_session(request: SessionRequest) -> SessionResponse:
    session = _load_session(request.session)
    topic = _session_topic(session)
    context = _analysis_context(session)

    observation_ids = {item.question_id for item in topic.observation_questions}
    prediction_ids = {item.question_id for item in topic.prediction_questions}
    answers = _latest_answers(session.observation_answers, observation_ids)
    if set(answers) != observation_ids:
        raise HTTPException(status_code=409, detail="observation_answers_incomplete")

    try:
        review = review_observations(
            topic,
            answers,
            context,
            learning_tutor,
            prediction_answers=_latest_answers(session.prediction_answers, prediction_ids),
        )
        apply_observation_review(session, review, learning_state_machine)
        if session.current_step is LearningStep.FEEDBACK_READY:
            learning_state_machine.transition(session, LearningStep.SESSION_COMPLETE)
    except (InvalidLearningTransition, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        if session.current_step is LearningStep.OBSERVATION_SUBMITTED:
            learning_state_machine.fail(session, "learning_feedback_failed")
        raise HTTPException(status_code=502, detail="learning_feedback_failed") from error
    return SessionResponse(session=session.to_dict())


def _analysis_context(session: LearningSession):
    from backend.learning.analysis_schemas import LearningAnalysisContext

    if not session.analysis_snapshot:
        raise HTTPException(status_code=409, detail="analysis_result_required")
    try:
        return LearningAnalysisContext.from_dict(session.analysis_snapshot)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=409, detail="invalid_analysis_snapshot") from error


# Case 안에서 묻는 AI 자유질문. I-V/Field 자유질문과 달리 이 대화는 학습
# 세션에 붙어 있어서 followup_history로 함께 저장된다.
@router.post("/case-study/sessions/followup")
def ask_followup(request: FollowupRequest) -> FollowupResponsePayload:
    session = _load_session(request.session)
    topic = _session_topic(session)
    context = _analysis_context(session)
    # FollowupTurn에는 to_dict가 없다. 데스크톱 앱이 손으로 고르는 필드를
    # 그대로 맞춘다 (panel.py의 history_data) — 여기서 더 넣거나 빼면 튜터가
    # 받는 맥락이 두 앱에서 달라진다.
    history = [
        {
            "question": turn.question,
            "answer": turn.answer,
            "question_type": turn.question_type,
            "matched_concepts": turn.matched_concepts,
            "source": turn.source,
            "interpreted_intent": turn.interpreted_intent,
            "pipeline_diagnostics": turn.pipeline_diagnostics,
        }
        for turn in session.followup_history
    ]
    try:
        response = learning_tutor.ask_followup(
            topic,
            request.question,
            context,
            history,
            session.dialogue_state.to_dict(),
            {
                "understanding_level": session.understanding_level.value,
                "completed_concepts": session.completed_concepts,
                "remaining_concepts": session.remaining_concepts,
                "detected_misconceptions": session.detected_misconceptions,
            },
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="learning_followup_failed") from error
    LearningLLMService.record_followup(session, request.question, response)
    return FollowupResponsePayload(
        session=session.to_dict(),
        answer=response.answer,
        source=response.source,
    )
