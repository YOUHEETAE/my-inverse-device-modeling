/**
 * 이 화면이 로컬 실행판(standalone/) 안에서 도는지.
 *
 * `npm run build:standalone`이 web/.env.standalone을 읽어 켜준다. 배포판
 * 빌드에서는 값이 없으므로 항상 false다 — 두 빌드의 차이는 이 플래그 하나뿐이고,
 * 화면 코드는 한 벌만 유지한다.
 *
 * 로컬 실행판에는 LLM 키가 없다. 키를 실행 파일에 넣으면 압축만 풀어도 꺼낼 수
 * 있어서 넣지 않는다. 그래서 AI 응답만 빠지고, 예측·비교·Case Study 채점은
 * 그대로 돈다(채점은 정답표 대조라 LLM이 필요 없다).
 */
export const IS_STANDALONE = import.meta.env.VITE_STANDALONE === "1";
