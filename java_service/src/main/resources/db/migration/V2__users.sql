-- 계정 테이블. 소셜 로그인(구글/카카오/네이버)만 지원하므로 비밀번호 컬럼이
-- 없다.
--
-- 이미 적용된 마이그레이션은 수정하면 체크섬이 어긋나 기동이 막힌다. 이
-- 파일은 아직 배포된 적이 없어서 로컬 DB만 비우고 다시 쓴 것이고, 배포가
-- 시작된 뒤로는 변경을 항상 새 번호 파일로 추가해야 한다.

CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    -- 어느 서비스로 로그인했는지. 값은 application.properties의
    -- spring.security.oauth2.client.registration.<여기> 와 같은 문자열이다.
    provider    VARCHAR(20)  NOT NULL,
    -- 제공자 쪽 고유 ID (구글 sub, 카카오/네이버 id). 이메일은 사용자가
    -- 바꿀 수 있지만 이 값은 바뀌지 않아서 식별자로 쓴다.
    provider_id VARCHAR(255) NOT NULL,
    -- 카카오는 사용자가 이메일 제공에 동의하지 않으면 주지 않으므로 nullable.
    -- UNIQUE를 걸지 않은 이유: 같은 사람이 구글과 카카오로 각각 로그인하면
    -- 같은 이메일로 두 행이 생기는데, UNIQUE면 두 번째 로그인이 실패한다.
    email       VARCHAR(255),
    name        VARCHAR(255) NOT NULL,
    -- 서버는 UTC, 사용자는 KST라 시간대 정보를 함께 저장한다.
    created_at  TIMESTAMPTZ  NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL,

    -- provider_id는 각 제공자 안에서만 고유하다(카카오 12345번과 네이버
    -- 12345번은 다른 사람). 그래서 둘을 묶어야 유일해진다.
    CONSTRAINT users_provider_uk UNIQUE (provider, provider_id)
);
