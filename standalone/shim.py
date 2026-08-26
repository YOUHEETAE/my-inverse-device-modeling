"""배포판에서 자바 서비스가 맡던 경로들.

프론트엔드는 두 종류의 API를 부른다. 예측·이론·케이스 내용처럼 계산이
필요한 것은 Python이 직접 서빙하고, 로그인·대화 저장·학습 세션 저장은
자바가 맡는다. 실행 파일에는 자바가 없으므로 그 두 번째 묶음을 여기서
채운다.

Python 라우터를 HTTP로 다시 부르지 않고 함수로 직접 호출한다. 같은
프로세스 안이라 자기 자신에게 요청을 보낼 이유가 없고, 포트가 무엇인지
알 필요도 없어진다.

자바와 다른 점이 하나 있다. 계정이 없으므로 소유자 검사가 사라진다 —
남의 기록을 볼 수 있는 상황 자체가 없기 때문이다. 하루 한도와 초당 제한도
빠진다. 그건 여러 사람이 함께 쓰는 서버의 사정이지 로컬 실행판의 것이
아니다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.routers.case_study import (
    AnswerRequest,
    FollowupRequest,
    NewSessionRequest,
    PortfolioRequest,
    SessionRequest,
    ask_followup,
    begin_prediction,
    case_study_portfolio,
    create_case_study_session,
    evaluate_session,
    recover_session,
    regenerate_experiment,
    reset_case_study_session,
    run_experiment,
    submit_observations,
    submit_predictions,
)
from app.routers.explain import (
    ExplainCurveChatRequest,
    ExplainFieldChatRequest,
    explain_curves_chat,
    explain_fields_chat,
)

from standalone import local_store

router = APIRouter()

# 배포판 자바의 ChatService와 같은 값. 여기서도 유지하는 이유는 화면이
# "20개 중 3개 사용" 같은 표시를 그 값으로 그리기 때문이다.
HISTORY_TURNS = 6
MAX_TURNS_PER_THREAD = 20
THREAD_LIMIT = 20
MESSAGE_LIMIT = 200


# ---- 로그인 ------------------------------------------------------------
#
# 구글 OAuth는 인터넷과 실제 client secret을 요구하고, 그 값을 실행 파일에
# 넣으면 추출된다. 그래서 로컬판은 사용자가 한 명뿐인 것으로 두고 항상
# 로그인된 상태를 돌려준다 — 화면의 기능 잠금이 전부 이 응답을 보고
# 결정되므로, 이렇게 해야 배포판과 같은 화면이 나온다.


@router.get("/auth/me")
def me() -> dict[str, Any]:
    return {
        "authenticated": True,
        "user_id": 1,
        "name": "로컬 사용자",
        "email": None,
    }


@router.post("/logout")
def logout() -> Response:
    # 끊을 세션이 없다. 화면은 새로 불러오면서 상태를 비운다.
    return Response(status_code=204)


# ---- 자유질문 ----------------------------------------------------------


class CurveChatBody(BaseModel):
    curves: list[dict[str, Any]]
    question: str = Field(min_length=1, max_length=800)
    thread_id: int | None = None


class FieldChatBody(BaseModel):
    fields: list[dict[str, Any]]
    display: str
    scale_mode: str
    range_mode: str
    question: str = Field(min_length=1, max_length=800)
    thread_id: int | None = None


@router.post("/chat/curves")
def chat_curves(body: CurveChatBody) -> dict[str, Any]:
    return _ask(
        body.thread_id,
        kind="curves",
        device_config={"curves": body.curves},
        question=body.question,
        call=lambda config, history, checkpoint: explain_curves_chat(
            ExplainCurveChatRequest(
                curves=config["curves"],
                question=body.question,
                history=history,
                intent_checkpoint=checkpoint,
            )
        ),
    )


@router.post("/chat/fields")
async def chat_fields(body: FieldChatBody) -> dict[str, Any]:
    return await _ask_async(
        body.thread_id,
        kind="fields",
        device_config={
            "fields": body.fields,
            "display": body.display,
            "scale_mode": body.scale_mode,
            "range_mode": body.range_mode,
        },
        question=body.question,
        call=lambda config, history, checkpoint: explain_fields_chat(
            ExplainFieldChatRequest(
                fields=config["fields"],
                display=config["display"],
                scale_mode=config["scale_mode"],
                range_mode=config["range_mode"],
                question=body.question,
                history=history,
                intent_checkpoint=checkpoint,
            )
        ),
    )


def _context(thread_id: int | None, device_config: dict[str, Any]):
    """이 질문이 쓸 소자 설정·이력·intent 체크포인트."""
    if thread_id is None:
        # 첫 질문이 설정을 얼린다. 이후 질문은 요청에 실려온 설정을 쓰지
        # 않는다 — 그래야 화면을 바꿔도 대화가 같은 소자를 얘기한다.
        return device_config, [], {}
    stored = local_store.thread(thread_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    if local_store.turn_count(thread_id) >= MAX_TURNS_PER_THREAD:
        raise HTTPException(
            status_code=409,
            detail=f"이 대화는 질문 {MAX_TURNS_PER_THREAD}개를 채웠습니다. 새 대화를 시작해 주세요.",
        )
    return (
        stored["device_config"],
        local_store.recent_turns(thread_id, HISTORY_TURNS),
        local_store.last_checkpoint(thread_id),
    )


def _reply(thread_id: int | None, kind: str, config: dict[str, Any], question: str, answer) -> dict[str, Any]:
    # 대화는 답을 받은 뒤에 만든다. 먼저 만들면 실패했을 때 빈 대화가 남는다.
    if thread_id is None:
        thread_id = local_store.create_thread(kind, config)
    turns_used = local_store.append_message(
        thread_id, question, answer.answer, answer.source, answer.intent, answer.intent_checkpoint
    )
    return {
        "thread_id": thread_id,
        "answer": answer.answer,
        "source": answer.source,
        "intent": answer.intent,
        "used_evidence_ids": list(answer.used_evidence_ids),
        "suggested_followup": answer.suggested_followup,
        "needs_new_experiment": answer.needs_new_experiment,
        "turns_used": turns_used,
        "turn_limit": MAX_TURNS_PER_THREAD,
    }


def _ask(thread_id, *, kind, device_config, question, call) -> dict[str, Any]:
    config, history, checkpoint = _context(thread_id, device_config)
    return _reply(thread_id, kind, config, question, call(config, history, checkpoint))


async def _ask_async(thread_id, *, kind, device_config, question, call) -> dict[str, Any]:
    config, history, checkpoint = _context(thread_id, device_config)
    return _reply(thread_id, kind, config, question, await call(config, history, checkpoint))


@router.get("/chat/threads")
def list_threads(kind: str | None = None) -> list[dict[str, Any]]:
    result = []
    for record in local_store.threads(kind, THREAD_LIMIT):
        messages = record["messages"]
        result.append({
            "thread_id": record["thread_id"],
            "kind": record["kind"],
            "updated_at": record["updated_at"],
            # 마지막이 아니라 첫 질문 — 대화의 주제를 정한 쪽이라 식별에 쓸 수 있다.
            "first_question": messages[0]["question"] if messages else None,
            "device_config": record["device_config"],
            "turns_used": local_store.turn_count(record["thread_id"]),
        })
    return result


@router.get("/chat/threads/{thread_id}")
def get_thread(thread_id: int) -> dict[str, Any]:
    record = local_store.thread(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return {
        "thread_id": record["thread_id"],
        "kind": record["kind"],
        "device_config": record["device_config"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "messages": [
            {
                "id": m["id"],
                "question": m["question"],
                "answer": m["answer"],
                "source": m["source"],
                "intent": m.get("intent"),
                "created_at": m["created_at"],
            }
            for m in record["messages"][:MESSAGE_LIMIT]
        ],
        "turns_used": local_store.turn_count(thread_id),
        "turn_limit": MAX_TURNS_PER_THREAD,
    }


# ---- 학습 세션 ----------------------------------------------------------
#
# 걸음마다 모양이 같다: 저장된 세션을 꺼내 Python에 넘기고, 돌아온 세션을
# 저장한다. 배포판의 LearningService.advance가 하는 일과 같다.


class RenameBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class AnswersBody(BaseModel):
    answers: dict[str, Any]


class QuestionBody(BaseModel):
    question: str = Field(min_length=1, max_length=800)


def _require(session_id: str) -> dict[str, Any]:
    session = local_store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="학습 기록을 찾을 수 없습니다.")
    return session


def _advance(session_id: str, call) -> dict[str, Any]:
    """세션 한 걸음. 갱신된 세션만 화면으로 돌려준다."""
    response = call(_require(session_id))
    return local_store.save_session(response.session)


@router.get("/case-study/portfolio")
def portfolio() -> dict[str, Any]:
    return case_study_portfolio(PortfolioRequest(sessions=local_store.all_sessions()))


@router.get("/case-study/sessions")
def list_sessions(topic_id: str | None = None) -> list[dict[str, Any]]:
    return local_store.session_summaries(topic_id)


@router.get("/case-study/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return _require(session_id)


@router.post("/case-study/sessions")
def create_session(body: NewSessionRequest) -> dict[str, Any]:
    return local_store.save_session(create_case_study_session(body).session)


@router.patch("/case-study/sessions/{session_id}")
def rename(session_id: str, body: RenameBody) -> Response:
    if not local_store.rename_session(session_id, body.display_name):
        raise HTTPException(status_code=404, detail="학습 기록을 찾을 수 없습니다.")
    return Response(status_code=200)


@router.delete("/case-study/sessions/{session_id}", status_code=204)
def delete(session_id: str) -> Response:
    if not local_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="학습 기록을 찾을 수 없습니다.")
    return Response(status_code=204)


@router.post("/case-study/sessions/{session_id}/reset")
def reset(session_id: str) -> dict[str, Any]:
    return _advance(session_id, lambda s: reset_case_study_session(SessionRequest(session=s)))


@router.post("/case-study/sessions/{session_id}/recover")
def recover(session_id: str) -> dict[str, Any]:
    return _advance(session_id, lambda s: recover_session(SessionRequest(session=s)))


@router.post("/case-study/sessions/{session_id}/begin-prediction")
def begin(session_id: str) -> dict[str, Any]:
    return _advance(session_id, lambda s: begin_prediction(SessionRequest(session=s)))


@router.post("/case-study/sessions/{session_id}/predictions")
def predictions(session_id: str, body: AnswersBody) -> dict[str, Any]:
    return _advance(
        session_id,
        lambda s: submit_predictions(AnswerRequest(session=s, answers=body.answers)),
    )


@router.post("/case-study/sessions/{session_id}/observations")
def observations(session_id: str, body: AnswersBody) -> dict[str, Any]:
    return _advance(
        session_id,
        lambda s: submit_observations(AnswerRequest(session=s, answers=body.answers)),
    )


@router.post("/case-study/sessions/{session_id}/evaluation")
def evaluation(session_id: str) -> dict[str, Any]:
    return _advance(session_id, lambda s: evaluate_session(SessionRequest(session=s)))


@router.post("/case-study/sessions/{session_id}/experiment")
def experiment(session_id: str) -> dict[str, Any]:
    """모델 추론이 도는 단계. 갱신된 세션과 그릴 곡선이 함께 온다."""
    response = run_experiment(SessionRequest(session=_require(session_id)))
    local_store.save_session(response.session)
    # 곡선은 저장하지 않는다 — 세션에 넣으면 걸음마다 오가는 짐이 되고,
    # 조건만 있으면 언제든 다시 만들 수 있다.
    return {"session": response.session, "result": response.result.model_dump()}


@router.post("/case-study/sessions/{session_id}/regenerate")
def regenerate(session_id: str) -> dict[str, Any]:
    """저장된 세션을 다시 열었을 때 그래프만 되살린다. 세션은 그대로 둔다."""
    return regenerate_experiment(SessionRequest(session=_require(session_id))).model_dump()


@router.post("/case-study/sessions/{session_id}/followup")
def followup(session_id: str, body: QuestionBody) -> dict[str, Any]:
    response = ask_followup(
        FollowupRequest(session=_require(session_id), question=body.question)
    )
    local_store.save_session(response.session)
    return {"answer": response.answer, "source": response.source}
