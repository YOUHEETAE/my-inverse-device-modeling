// 얼린 소자 설정을 상태줄 한 줄로 요약한다. 데스크톱 앱은 라벨만
// 보여주지만("Curve 1, Curve 2 스냅샷 기준"), 웹에서는 파라미터를 바꿔도
// 라벨이 그대로라 어느 설정이었는지 구분되지 않는다. 그래서 달라지는
// 파라미터를 함께 적는다.
interface Labelled {
  label?: string;
  [key: string]: unknown;
}

const PARAMETER_KEYS = ["L", "T", "B", "SD", "LDD"] as const;

export function summarizeConfig(config: unknown): string | null {
  if (!config || typeof config !== "object") return null;
  const record = config as Record<string, unknown>;
  const devices = (record.curves ?? record.fields) as Labelled[] | undefined;
  if (!Array.isArray(devices) || devices.length === 0) return null;

  // 소자들 사이에서 실제로 다른 파라미터만 적는다 — 전부 나열하면 길어서
  // 읽히지 않고, 하나뿐이면 비교할 게 없으니 대표값을 쓴다.
  const varying = PARAMETER_KEYS.filter(
    (key) => new Set(devices.map((d) => String(d[key] ?? ""))).size > 1,
  );
  const keys = varying.length > 0 ? varying : (["L"] as const);

  const parts = devices.map((d) => keys.map((k) => `${k}=${d[k]}`).join(" "));
  const summary = parts.join(" / ");

  // Field는 표시 종류에 따라 답이 완전히 달라져서 같이 얼린다.
  const display = typeof record.display === "string" ? record.display : null;
  return display ? `${summary} · ${display}` : summary;
}
