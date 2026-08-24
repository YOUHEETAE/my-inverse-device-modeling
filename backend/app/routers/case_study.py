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
    # 카드에 "변경 조건: Channel length: 700 nm -> 300 nm"으로 보여주는 값
    changed_parameters: list[str]
    baseline_label: str
    comparison_label: str


class SafeQuestion(BaseModel):
    question_id: str
    type: str
    prompt: str
    options: list[str]
    reason_required: bool


class TopicDetail(TopicSummary):
    learning_objectives: list[str]
    baseline_conditions: dict[str, float]
    comparison_conditions: dict[str, float]
    condition_descriptions: dict[str, str]
    theory_concepts: list[str]
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


class SessionResponse(BaseModel):
    session: dict[str, Any]


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
    return SafeQuestion(
        question_id=question.question_id,
        type=question.type,
        prompt=question.prompt,
        options=list(question.options),
        reason_required=question.reason_required,
    )


def _summary(topic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "title": topic.title,
        "description": topic.description,
        "catalog_order": topic.catalog_order,
        "prerequisite_topic_ids": list(topic.prerequisite_topic_ids),
        "changed_parameters": list(
            compare_conditions(topic.baseline_conditions, topic.comparison_conditions)
        ),
        "baseline_label": topic.baseline_label,
        "comparison_label": topic.comparison_label,
    }


def compare_conditions(baseline: dict[str, float], comparison: dict[str, float]) -> tuple[str, ...]:
    return tuple(key for key in baseline if baseline.get(key) != comparison.get(key))


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
@router.post("/case-study/sessions/experiment")
def run_experiment(request: SessionRequest) -> SessionResponse:
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
    return SessionResponse(session=session.to_dict())


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
