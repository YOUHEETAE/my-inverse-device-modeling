from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.learning.topics import TopicConfigError, load_topics


class TopicSummary(BaseModel):
    topic_id: str
    title: str
    description: str
    catalog_order: int
    prerequisite_topic_ids: list[str]


class ExperimentConditions(BaseModel):
    L: float
    T: float
    B: float
    SD: float
    LDD: float


class SafeQuestion(BaseModel):
    question_id: str
    type: str
    prompt: str
    options: list[str]
    reason_required: bool


class TopicDetail(BaseModel):
    topic_id: str
    title: str
    description: str
    learning_objectives: list[str]
    baseline: ExperimentConditions
    comparison: ExperimentConditions
    prediction_questions: list[SafeQuestion]
    observation_questions: list[SafeQuestion]


class AnswerSubmission(BaseModel):
    question_id: str
    selected: list[str]
    reason: str = ""


class GradeRequest(BaseModel):
    prediction_answers: list[AnswerSubmission]
    observation_answers: list[AnswerSubmission]


class QuestionResult(BaseModel):
    question_id: str
    prompt: str
    correct_options: list[str]
    selected: list[str]
    fully_correct: bool


class GradeResponse(BaseModel):
    positive_feedback: list[str]
    corrections: list[str]
    summary: str
    question_results: list[QuestionResult]


router = APIRouter()


def _load_topics_or_500() -> dict:
    try:
        return load_topics()
    except TopicConfigError as error:
        raise HTTPException(status_code=500, detail=f"Case Study config error: {error}")


def _safe_question(question) -> SafeQuestion:
    return SafeQuestion(
        question_id=question.question_id,
        type=question.type,
        prompt=question.prompt,
        options=list(question.options),
        reason_required=question.reason_required,
    )


@router.get("/case-study/topics")
def list_case_study_topics() -> list[TopicSummary]:
    topics = _load_topics_or_500()
    return [
        TopicSummary(
            topic_id=topic.topic_id,
            title=topic.title,
            description=topic.description,
            catalog_order=topic.catalog_order,
            prerequisite_topic_ids=list(topic.prerequisite_topic_ids),
        )
        for topic in topics.values()
    ]


@router.get("/case-study/topics/{topic_id}")
def get_case_study_topic(topic_id: str) -> TopicDetail:
    topic = _load_topics_or_500().get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown case study topic: {topic_id}")
    # Answer keys (correct_options / concepts_by_option / misconceptions_by_option)
    # are intentionally left out of this response — they're only used
    # server-side in /grade, once the learner has already submitted answers.
    return TopicDetail(
        topic_id=topic.topic_id,
        title=topic.title,
        description=topic.description,
        learning_objectives=list(topic.learning_objectives),
        baseline=ExperimentConditions(**topic.baseline_conditions),
        comparison=ExperimentConditions(**topic.comparison_conditions),
        prediction_questions=[_safe_question(q) for q in topic.prediction_questions],
        observation_questions=[_safe_question(q) for q in topic.observation_questions],
    )


def _grade_question(question, submitted: AnswerSubmission | None) -> tuple[QuestionResult, list[str], list[str]]:
    selected = list(submitted.selected) if submitted else []
    correct = list(question.correct_options)
    positive: list[str] = []
    corrections: list[str] = []
    for option in selected:
        if option in correct:
            positive.append(f"[{question.prompt}] '{option}' — 정확하게 예측했습니다.")
        elif question.misconceptions_by_option.get(option):
            corrections.append(f"[{question.prompt}] '{option}'은(는) 흔히 하는 오해입니다. 결과를 다시 살펴보세요.")
        else:
            corrections.append(f"[{question.prompt}] '{option}'은(는) 이번 조건 변화의 핵심 결과와는 거리가 있습니다.")
    for option in correct:
        if option not in selected:
            corrections.append(f"[{question.prompt}] '{option}'도 이번 변화에서 함께 확인해야 합니다.")
    fully_correct = (set(selected) == set(correct)) if correct else True
    return (
        QuestionResult(
            question_id=question.question_id,
            prompt=question.prompt,
            correct_options=correct,
            selected=selected,
            fully_correct=fully_correct,
        ),
        positive,
        corrections,
    )


@router.post("/case-study/topics/{topic_id}/grade")
def grade_case_study(topic_id: str, request: GradeRequest) -> GradeResponse:
    topic = _load_topics_or_500().get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"Unknown case study topic: {topic_id}")

    by_id = {answer.question_id: answer for answer in (*request.prediction_answers, *request.observation_answers)}
    all_questions = (*topic.prediction_questions, *topic.observation_questions)

    positive_all: list[str] = []
    corrections_all: list[str] = []
    results: list[QuestionResult] = []
    for question in all_questions:
        result, positive, corrections = _grade_question(question, by_id.get(question.question_id))
        results.append(result)
        positive_all.extend(positive)
        corrections_all.extend(corrections)

    correct_count = sum(1 for result in results if result.fully_correct)
    summary = f"{len(results)}개 질문 중 {correct_count}개를 정확히 예측·관찰했습니다."

    return GradeResponse(
        positive_feedback=positive_all,
        corrections=corrections_all,
        summary=summary,
        question_results=results,
    )
