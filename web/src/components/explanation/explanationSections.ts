/**
 * 자동 분석 응답을 화면에 그릴 섹션으로 나눈다.
 *
 * 서버가 네 갈래로 나눠 보내는데(descriptions/comparisons/tradeoffs/cautions)
 * 웹은 그걸 그냥 이어 붙여서, 어디까지가 관찰이고 어디부터가 비교인지
 * 구분되지 않았다. 데스크톱은 각 덩어리에 제목을 붙인다.
 *
 * 제목과 조립 규칙은 backend/explanation/schemas.py의 display_text와 같다 —
 * 외부 LLM 답변은 이미 문장으로 이어져 있어 한 문단으로 두고, mock 답변은
 * 항목이 끊어져 있어 불릿으로 나눈다.
 */
export interface ExplanationSection {
  title: string;
  lines: string[];
  /** 문단 하나로 이을지, 항목으로 나눌지. */
  paragraph: boolean;
}

interface SectionSource {
  descriptions: string[];
  comparisons: string[];
  tradeoffs: string[];
  cautions: string[];
  provider?: string;
}

const TITLES = [
  ["결과 설명", "descriptions"],
  ["비교", "comparisons"],
  ["Trade-off", "tradeoffs"],
  ["주의사항", "cautions"],
] as const;

export function toSections(result: SectionSource | null): ExplanationSection[] {
  if (!result) return [];
  const paragraph = result.provider === "external_llm";
  return TITLES.map(([title, key]) => ({
    title,
    lines: (result[key] ?? []).filter((line) => line.trim().length > 0),
    paragraph,
  })).filter((section) => section.lines.length > 0);
}
