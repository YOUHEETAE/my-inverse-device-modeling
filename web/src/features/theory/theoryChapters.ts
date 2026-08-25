// 장 목록과 카드에 들어갈 소개만 — 본문 JSX는 TheoryPage가 들고 있다.
// 여기에 KaTeX와 시뮬레이터가 딸려오지 않아야 목록만 필요한 쪽에서 가볍게
// 가져다 쓸 수 있다.
export interface TheoryChapter {
  id: string;
  label: string;
  /** 카드 한 줄 소개. 각 장 도입부를 줄인 것이다. */
  summary: string;
  /** 그 장에서 다루는 주제. 카드 아래에 가운뎃점으로 이어 붙인다. */
  topics: string[];
  /** 이 장에 딸린 대화형 도구. 1·2장에만 있다. */
  tool?: string;
}

export const THEORY_CHAPTERS: TheoryChapter[] = [
  {
    id: "chapter1",
    label: "1. PN Junction",
    summary:
      "MOSFET의 Source·Drain은 Body와 PN 접합을 이룹니다. 도핑 농도와 바이어스에 따라 공핍영역·전기장·전위·에너지 밴드가 어떻게 달라지는지 봅니다.",
    topics: [
      "공핍영역과 Built-in Potential",
      "포아송 방정식",
      "공핍층 폭과 도핑",
      "Band Bending",
      "순방향/역방향 바이어스",
    ],
    tool: "PN 접합 시뮬레이터",
  },
  {
    id: "chapter2",
    label: "2. Long-Channel MOSFET",
    summary:
      "Gate 전압이 채널을 만들고 Drain 전압이 전류를 흐르게 하는 기본 동작. Drain의 영향이 Source까지 닿지 않는 이상적인 조건에서 봅니다.",
    topics: [
      "Accumulation·Depletion·Inversion",
      "문턱전압",
      "Linear/Saturation/Cutoff",
      "Id–Vg와 Id–Vd",
      "Curve와 Field Map의 연결",
    ],
    tool: "MOS Capacitor 시뮬레이터",
  },
  {
    id: "chapter3",
    label: "3. Short-Channel MOSFET",
    summary:
      "채널이 짧아지면 채널 전위를 Gate 혼자 결정하지 못합니다. Source와 Drain이 끼어들면서 생기는 문제들을 봅니다.",
    topics: [
      "Charge Sharing",
      "Vth Roll-off",
      "DIBL",
      "Punch-through",
      "Ion–Ioff Trade-off",
    ],
  },
  {
    id: "chapter4",
    label: "4. MOSFET Performance Enhancement",
    summary:
      "Short-Channel Effect를 줄이는 두 방향 — Gate의 제어력을 키우거나, Source·Drain의 침투를 막거나. 시뮬레이션에 실제로 들어 있는 LDD를 중심으로 봅니다.",
    topics: [
      "LDD의 전기장 완화 원리",
      "LDD와 Series Resistance Trade-off",
      "산화막 두께와 Body 도핑",
      "Halo Implant",
    ],
  },
  {
    id: "chapter5",
    label: "5. Python TCAD",
    summary:
      "앞의 결과들이 어떻게 계산됐는지. DEVSIM이 mesh 위에 방정식을 세우고 푸는 과정과, 수렴한 결과를 어디까지 믿어도 되는지 봅니다.",
    topics: [
      "Mesh와 영역 정의",
      "Drift–Diffusion",
      "Newton Solver",
      "Bias Sweep",
      "결과 검증과 모델 범위",
    ],
  },
];
