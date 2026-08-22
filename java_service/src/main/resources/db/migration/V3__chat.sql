-- 자유질문 대화 기록.
--
-- Python 쪽 채팅 서비스는 상태를 갖지 않는다 — answer()가 이전 대화를 인자로
-- 받는다. Tkinter는 그 이력을 메모리에 들고 있었지만, 웹에서는 여기 저장해서
-- 새로고침하거나 다른 기기에서 열어도 이어지게 한다.
--
-- LLM에는 최근 2턴만 전달되므로(iv_chat.py가 잘라냄) 전부 저장한다고 해서
-- 추론 비용이 늘지는 않는다. 저장 목적은 화면 표시와 학습 기록이다.

-- 하나의 분석을 대상으로 한 대화 묶음. Tkinter가 새 예측을 돌릴 때마다 대화를
-- 초기화하는 것과 같은 단위다 — 소자 조건이 바뀌면 이전 대화는 맥락이 맞지
-- 않기 때문.
CREATE TABLE chat_thread (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 'curves' | 'fields'
    kind       VARCHAR(16)  NOT NULL,
    -- 질문 당시의 소자 조건(L/T/B/SD/LDD 등). 나중에 "그때 무슨 설정으로
    -- 물어봤더라"를 복원할 수 있게 통째로 남긴다.
    device_config JSONB     NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 사용자별 최근 대화 목록 조회용.
CREATE INDEX chat_thread_user_idx ON chat_thread (user_id, updated_at DESC);

-- 질문과 답변을 한 행에 담는다. Python이 주고받는 history 단위가
-- {question, answer}라서 그 모양을 그대로 유지하면 변환이 없다.
CREATE TABLE chat_message (
    id         BIGSERIAL PRIMARY KEY,
    thread_id  BIGINT       NOT NULL REFERENCES chat_thread(id) ON DELETE CASCADE,
    question   TEXT         NOT NULL,
    answer     TEXT         NOT NULL,
    -- 'external_llm' | 'local_router' | 'external_error'.
    -- external_error인 턴은 다음 질문의 맥락으로 되돌려보내지 않는다(Python도
    -- 같은 기준으로 걸러낸다).
    source     VARCHAR(32)  NOT NULL,
    intent     VARCHAR(64),
    -- 명확화 흐름을 이어가려면 마지막 턴의 값이 필요하다.
    intent_checkpoint JSONB,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX chat_message_thread_idx ON chat_message (thread_id, created_at);
