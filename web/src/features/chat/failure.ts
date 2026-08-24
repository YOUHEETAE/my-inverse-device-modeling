// 서버가 내려주는 실패 메시지를 화면에서 쓰기 좋게 쪼갠다.
//
// 내용을 새로 지어내지 않는다 — 무엇을 보여줄 수 있는지는
// docs/user_information_boundary.md가 정하고 있고(공개 가능: 실패 범주,
// 조치, 재시도 대기, 보존 여부 / 금지: 검증 코드, 파이프라인 단계, provider
// 정보), backend/public_presentation.py가 그 규칙대로 이미 문장을 만든다.
// 같은 문서가 "UI code formats only the public category, action, retry wait,
// and preservation state"라고 형식화를 UI 몫으로 지정한다. 여기서 하는 일이
// 정확히 그것이다.
//
// 형식 (public_ai_failure_message):
//   I-V AI 답변을 생성하지 못했습니다.
//   상태: …
//   원인: …
//   다시 시도: …
//   완료된 질문 해석 결과는 보존됩니다.   (있을 때만)
export interface ChatFailure {
  /** 사람이 먼저 읽어야 할 한 줄 */
  reason: string;
  /** 무엇을 하면 되는지 */
  action: string | null;
  /** 질문 해석 등이 남아 있는지 */
  preserved: string | null;
  /** 재시도가 의미 있는 경우 (조치가 "다시 시도"류일 때) */
  retryable: boolean;
  /**
   * 한도 초과처럼 최소 대기가 있는 경우의 초. 바로 다시 누르면 또 실패하므로
   * 버튼이 이만큼 기다린다. (경계 문서가 공개를 허용하는 값 — "whether retry
   * is useful and the minimum wait when known")
   */
  waitSeconds: number | null;
}

const PREFIX = { cause: "원인:", action: "다시 시도:", status: "상태:" };

export function parseFailure(answer: string): ChatFailure {
  const lines = answer
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const pick = (prefix: string) =>
    lines
      .find((l) => l.startsWith(prefix))
      ?.slice(prefix.length)
      .trim() ?? null;

  const action = pick(PREFIX.action);
  const preserved = lines.find((l) => l.includes("보존됩니다")) ?? null;

  const wait = action?.match(/(\d+)초 후/);

  return {
    // 원인이 곧 사람이 읽을 문장이다. 상태 줄은 범주 라벨이라 중복이라
    // 접어둔다. 형식이 예상과 다르면 통째로 보여주는 편이 안전하다.
    reason: pick(PREFIX.cause) ?? lines[0] ?? answer,
    action,
    preserved,
    retryable: action !== null && action.includes("다시 시도"),
    waitSeconds: wait ? Number(wait[1]) : null,
  };
}
