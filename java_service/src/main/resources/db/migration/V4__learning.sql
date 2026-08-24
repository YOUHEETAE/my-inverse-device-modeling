-- Case Study 학습 세션.
--
-- 데스크톱 앱은 세션을 로컬 JSON 파일에 둔다(JsonSessionRepository). 계정이
-- 없으니 그럴 수 있었지만, 웹은 로그인한 사용자별로 보관해야 한다.
--
-- session 컬럼에 Python의 LearningSession을 통째로 담는다. 필드를 쪼개
-- 컬럼으로 만들지 않는 이유는, 그 구조가 Python 소유이고(schema_version 2.0)
-- 예측 답변·분석 스냅샷·피드백·대화 이력이 계속 늘어나는 중첩 구조라서다.
-- 자바가 그걸 해석하기 시작하면 Python이 스키마를 고칠 때마다 같이 깨진다.
CREATE TABLE learning_session (
    -- Python이 발급한 UUID를 그대로 쓴다. 세션 안에도 같은 값이 들어 있어서
    -- 별도 키를 두면 두 값이 어긋날 수 있다.
    session_id   UUID         PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- 목록을 케이스별로 거르기 위해 밖으로 뺀다.
    topic_id     VARCHAR(64)  NOT NULL,
    session      JSONB        NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 학습 현황은 사용자의 모든 세션을 읽고, 케이스 화면은 그중 한 케이스만 읽는다.
CREATE INDEX learning_session_user_idx ON learning_session (user_id, updated_at DESC);
CREATE INDEX learning_session_topic_idx ON learning_session (user_id, topic_id, updated_at DESC);
