# java-service

SemiScope AI의 외부 공개 API. Caddy가 `/api/*`를 이 서비스로 보내고, 이
서비스가 기존 FastAPI 백엔드(`backend/`)를 호출한다. `backend/`는 그대로
남아있되 **내부 전용**이 되어, 외부에서 직접 접근할 수 없다.

```
브라우저 ──HTTPS──► Caddy ──► java_service:8080 ──► backend:8000
                                (공개 진입점)         (내부 전용)
```

마이그레이션 범위는 **라우터뿐**이다. ML/물리/LLM 코드(`ai/`, `tcad/`,
`backend/explanation/`, `backend/learning/`)는 Python에 그대로 두고
건드리지 않는다.

## 상태

6개 라우터 전부 이관 완료. 18개 엔드포인트가 Python 직접 호출과 상태
코드·응답 본문까지 동일함을 `scripts/verify_proxy_parity.py`로 검증한다.

| Java 컨트롤러 | 대응 Python 라우터 | 비고 |
|---|---|---|
| `parameters/ParametersController` | `parameters.py` | |
| `curves/CurvesController` | `curves.py` | |
| `fields/FieldsController` | `fields.py` | |
| `theory/TheoryController` | `theory.py` | `/theory/long-channel-mosfet/*`는 프론트가 더 이상 안 부르지만 동일성 유지를 위해 이관 |
| `explain/ExplainController` | `explain.py` | |
| `casestudy/CaseStudyController` | `case_study.py` | |

컨트롤러는 전부 순수 프록시라 자체 로직이 없다. 로직이 있는 건
`internal/` 패키지뿐이다.

## Rate limiting

Python의 slowapi는 **제거했다**. 이 서비스가 Python을 대신 호출하면 Python
입장에선 모든 요청이 한 IP(이 서비스)로 보여서 방문자별 제한이 무의미해지기
때문이다. 대신 여기서 실제 방문자 IP 기준으로 건다.

- 버스트 10개까지 허용, 초당 2개씩 리필 (`RateLimiterService`)
- 방문자 IP는 Caddy가 넣어주는 `X-Forwarded-For`에서 읽는다. Caddy가 이
  헤더를 덮어쓰기 때문에 클라이언트가 위조해서 우회할 수 없다
- CORS 프리플라이트(`OPTIONS`)는 카운트하지 않는다 — 브라우저가 자동으로
  보내는 사전 확인이라 사용자 행동이 아니다
- 안 쓰는 IP의 버킷은 1분마다 정리한다

## 프록시 뒤에서 동작하기

`server.forward-headers-strategy=FRAMEWORK`가 필요하다. Caddy가 TLS를
종료하고 평문 HTTP로 넘기기 때문에, 이게 없으면 스프링이 자기 주소를
`http://...:8080`으로 인식해서 **같은 출처에서 온 브라우저 요청도 CORS로
오판하고 403으로 막는다.**

## 응답 형식

- JSON 키는 snake_case (`fixed_biases`). `application.properties`의
  `spring.jackson.property-naming-strategy=SNAKE_CASE`로 한 번에 처리
- 디바이스 파라미터(`L`, `T`, `B`, `SD`, `LDD`)만 예외 — Python 필드명이
  대문자라, 그냥 두면 `l`/`t`로 직렬화된다. 해당 DTO마다 `@JsonProperty`로
  명시
- 에러는 Python과 같은 `{"detail": "..."}` 형태 (`ApiExceptionHandler`).
  스택트레이스는 노출하지 않는다

## 로컬 실행

프론트(`web/.env`)가 8080을 보므로 **세 개를 다 띄워야** 한다.

```bash
# 1. Python 백엔드
cd backend && uvicorn app.main:app --port 8000

# 2. 이 서비스
cd java_service && ./mvnw spring-boot:run     # 8080

# 3. 프론트엔드
cd web && npm run dev                          # 5174
```

Docker로 전체를 띄우려면 저장소 루트에서 `docker compose up -d --build`
(→ https://localhost).

## 테스트

```bash
mvn test                                       # 단위/슬라이스 테스트

python scripts/verify_proxy_parity.py          # Python과의 응답 동일성 (저장소 루트에서)
```

정합성 스크립트는 Python과 자바를 직접 띄워서 18개 엔드포인트를 비교하고
끝나면 정리한다. Python 응답을 목으로 대체하지 않는 이유는, 그러면 "내가
흉내낸 대로 자바가 전달하나"만 확인하는 꼴이라 실제로 발견됐던 버그들
(HTTP/1.1 협상 문제, Jackson 네이밍 문제)을 못 잡기 때문이다.

## 남은 것

- **인증/회원 기능** — 이 서비스를 자바로 분리한 원래 목적. 아직 시작 안 함
- **일일 사용량 제한** — 지금은 초당 제한만 있다. LLM 비용 통제용 일일
  한도는 정책을 정한 뒤 추가
- `backend`/`web` 컨테이너는 root로 실행된다 (이 서비스는 비root). Caddy는
  80/443을 열어야 해서 사정이 다르고, `backend`는 정리 가능
- 앞에 CDN이나 로드밸런서를 두게 되면 Caddy의 `trusted_proxies` 설정과
  IP 판별 로직을 다시 봐야 한다
