import type { ComponentType } from "react";
import {
  AlertTriangle,
  BarChart3,
  Calculator,
  FlaskConical,
  Layers,
  MessageSquareText,
  Sigma,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlowSteps } from "@/components/FlowSteps";

interface Feature {
  icon: ComponentType<{ className?: string }>;
  title: string;
  body: string[];
}

const FEATURES: Feature[] = [
  {
    icon: Sigma,
    title: "Theory",
    body: [
      "MOSFET의 기본 구조, 동작 원리, I–V 특성, 전기적 파라미터, 단채널 효과와 TCAD 해석 과정을 설명합니다.",
      "Theory에서 학습한 개념은 I–V Curve와 Field Map의 결과를 해석하는 기준으로 활용되며, 이론과 시뮬레이션 결과가 분리되지 않도록 구성합니다.",
    ],
  },
  {
    icon: BarChart3,
    title: "I–V Curve 예측",
    body: [
      "입력한 구조와 도핑 조건을 기반으로 MOSFET의 Id–Vg 및 Id–Vd Curve를 예측합니다.",
      "I–V Curve는 Linear Scale과 Log Scale로 확인할 수 있으며, 이를 통해 On 전류 뿐 아니라 Subthreshold 영역과 누설전류를 함께 분석할 수 있습니다.",
    ],
  },
  {
    icon: Calculator,
    title: "전기적 파라미터 추출",
    body: ["예측한 I–V Curve를 기반으로 주요 전기적 파라미터를 자동으로 추출합니다.", "이를 통해 사용자는 그래프의 형태만 확인하는 것이 아니라, 구조 변화에 따른 소자 성능의 변화를 정량적으로 비교할 수 있습니다."],
  },
  {
    icon: Layers,
    title: "Field Map 예측",
    body: [
      "MOSFET 내부의 Potential, Electric Field, Electron Density, Hole Density, Current Density를 공간 분포로 제공합니다.",
      "I–V Curve가 소자의 외부 전기적 응답을 보여준다면, Field Map은 해당 결과가 발생한 내부 원인을 확인하기 위한 자료가 됩니다. 전계 집중 위치, 채널 형성, Drain 전위의 영향 범위와 캐리어 분포 등을 관찰하여 구조와 전기적 특성 사이의 관계를 분석할 수 있습니다.",
    ],
  },
  {
    icon: MessageSquareText,
    title: "결과 해설",
    body: [
      "입력 조건과 예측 결과를 비교하여 주요 전기적 파라미터의 변화 방향과 변화량을 정리합니다. 또한 I–V Curve와 Field Map에서 확인해야 할 특징을 추출하고, 이를 MOSFET의 동작 원리와 연결하여 설명합니다.",
      "수치 계산과 결과 판정은 분석 코드에서 수행하며, LLM은 계산된 내용을 사용자가 이해하기 쉬운 문장으로 구성합니다. 따라서 LLM이 결과를 임의로 계산하거나 새로운 수치를 추정하는 것이 아니라, 검증된 분석 결과를 학습 언어로 전달하는 역할을 담당합니다.",
    ],
  },
  {
    icon: FlaskConical,
    title: "AI Case Study",
    body: [
      "Case Study는 주요 구조 변수를 중심으로 기준 구조와 비교 구조를 분석하는 가상 실험 기능입니다.",
      "사용자는 결과를 확인하기 전에 Ion, Ioff, Vth, DIBL 또는 Field Map의 변화를 예상합니다. 이후 실제 결과를 관찰하고, 자신의 예상과 분석 결과를 비교합니다.",
    ],
  },
];

const ELECTRICAL_PARAMETERS = [
  { symbol: "Vth", name: "Threshold Voltage" },
  { symbol: "Ion", name: "On Current" },
  { symbol: "Ioff", name: "Off Current" },
  { symbol: "SS", name: "Subthreshold Swing" },
  { symbol: "DIBL", name: "Drain-Induced Barrier Lowering" },
  { symbol: "gm_max", name: "Maximum Transconductance" },
  { symbol: "gds", name: "Output Conductance" },
  { symbol: "Ron", name: "On-resistance" },
  { symbol: "λ", name: "Channel Length Modulation Parameter" },
];

const CASE_STUDY_FEEDBACK = [
  "정확하게 이해한 부분",
  "보완이 필요한 개념",
  "그래프와 Field Map에서 확인할 근거",
  "구조 변화가 결과에 미친 물리적 원인",
  "성능 향상과 특성 악화 사이의 Trade-off",
  "이해를 확장하기 위한 다음 실험",
];

const AI_ROLES = [
  {
    label: "예측 AI",
    body: "MOSFET의 구조 및 도핑 조건을 입력받아 I–V Curve와 Field Map을 생성합니다. 이를 통해 사용자가 매번 TCAD 환경을 구성하고 수치해석을 수행하지 않아도 구조 변화에 따른 결과를 확인할 수 있도록 합니다.",
  },
  {
    label: "분석 AI",
    body: "예측된 결과에서 전기적 파라미터와 주요 변화를 분석합니다. 기준 조건과 변경 조건의 차이, 곡선의 변화, Field Map의 특징과 주요 Trade-off를 정리하고 이를 자연스러운 해설로 제공합니다.",
  },
  {
    label: "학습 AI",
    body: "Case Study에서 학습 주제에 적합한 비교 실험을 안내하고, 사용자의 사전 예상과 실제 결과를 비교합니다. 사용자의 이해 수준과 오개념에 따라 피드백을 제공하고, 원인을 추가로 확인할 수 있는 후속 실험을 제안합니다.",
  },
];

const APPROPRIATE_USES = [
  "구조 변수에 따른 변화 경향 확인",
  "I–V Curve와 Field Map의 해석 연습",
  "전기적 파라미터 사이의 Trade-off 학습",
  "MOSFET 이론과 시뮬레이션 결과의 연결",
  "주요 소자 현상에 대한 비교 실습",
];

export default function HomePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-8">
        {/* Hero */}
        <div>
          <h1 className="text-2xl font-bold leading-snug">AI-Based MOSFET Prediction and Learning Platform</h1>
          <p className="mt-3 text-base leading-[1.8] text-foreground">
            본 플랫폼은 MOSFET의 채널 길이, 산화막 두께, 소스·드레인 도핑, 바디 도핑, LDD 도핑을 입력하여 I–V Curve와 Field Map을 예측하는
            반도체 소자 학습 플랫폼입니다.
          </p>
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            예측된 I–V Curve에서는 Threshold Voltage, On Current, Off Current, Subthreshold Swing, DIBL, Transconductance, Output
            Conductance, On-resistance, Channel Length Modulation 등의 전기적 파라미터를 자동으로 추출합니다. Field Map에서는
            Potential, Electric Field, Electron Density, Hole Density, Current Density의 공간 분포를 확인할 수 있습니다.
          </p>
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            입력한 구조 조건과 예측 결과는 분석 과정을 거쳐 주요 변화와 물리적 의미로 정리됩니다. 이를 통해 사용자는 구조 및 도핑 조건의
            변화가 소자 내부의 전위와 전계, 캐리어 분포에 어떤 영향을 주며, 이러한 변화가 최종적인 전류 특성으로 어떻게 나타나는지 연결하여
            학습할 수 있습니다.
          </p>
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            Case Study에서는 결과를 단순히 확인하는 데 그치지 않고, 주요 구조 변수가 전기적 특성에 미치는 영향을 단계적으로 탐구합니다.
            사용자는 결과를 보기 전에 변화를 예상하고, 실제 I–V Curve와 Field Map을 관찰한 뒤 AI 피드백을 통해 자신의 이해를 점검할 수
            있습니다.
          </p>
        </div>

        {/* 목표 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">목표</h2>
          <Card>
            <CardContent className="flex flex-col gap-2 text-base leading-[1.8] text-foreground">
              <p>
                MOSFET의 구조 변화와 전기적 특성의 관계를 직접 확인하기 위해서는 일반적으로 TCAD 시뮬레이션이 활용됩니다. 그러나 TCAD를
                사용하려면 소자 구조 생성, Mesh 설정, 물리 모델 적용, 전압 조건 설정, 수렴 조정과 결과 후처리에 대한 이해가 필요합니다.
              </p>
              <p>
                이러한 과정은 반도체 소자를 처음 학습하는 사용자가 기본 개념을 실습하는 데 높은 진입장벽으로 작용합니다. 또한 상용 TCAD는
                고가의 라이선스와 별도의 실행 환경이 요구되기 때문에 대학, 연구기관 또는 기업에 소속되지 않은 일반 사용자가 자유롭게
                접근하기 어렵습니다.
              </p>
              <p>
                본 플랫폼은 복잡한 TCAD 설정과 계산 과정을 직접 수행하지 않고도 MOSFET의 구조 조건을 변경하고 그에 따른 결과를 비교할 수
                있는 학습 환경을 제공합니다. 단순한 결과 조회보다 다음 관계를 하나의 흐름으로 연결하는 것을 목표로 합니다.
              </p>
              <FlowSteps
                steps={["소자 구조 및 도핑 조건", "내부 물리 현상", "I–V 특성", "전기적 파라미터"]}
                className="my-1"
              />
              <p>
                이를 통해 사용자가 교재에서 학습한 MOSFET 이론을 실제 형태의 곡선과 공간 분포에 적용하고, 구조 변화에 따른 성능 향상과
                Trade-off를 직접 확인할 수 있도록 합니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* 기능 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">기능</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {FEATURES.map((feature) => (
              <Card key={feature.title}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <feature.icon className="h-4 w-4 text-primary" />
                    {feature.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm leading-[1.8] text-foreground">
                  {feature.body.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                  {feature.title === "전기적 파라미터 추출" && (
                    <ul className="grid grid-cols-1 gap-x-4 gap-y-1 rounded-sm border border-outline-variant bg-surface-container-low p-2 font-mono text-[11px] sm:grid-cols-2">
                      {ELECTRICAL_PARAMETERS.map((param) => (
                        <li key={param.symbol}>
                          <span className="font-semibold text-foreground">{param.symbol}</span>
                          <span className="text-on-surface-variant"> — {param.name}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {feature.title === "AI Case Study" && (
                    <>
                      <p>학습 AI는 사용자의 답변을 바탕으로 다음 내용을 제공합니다.</p>
                      <ul className="list-inside list-disc space-y-0.5 pl-1">
                        {CASE_STUDY_FEEDBACK.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                      <p>
                        이를 통해 Case Study를 미리 작성된 해설을 읽는 페이지가 아니라, 가설 설정·관찰·비교·피드백이 이어지는 학습
                        과정으로 구성합니다.
                      </p>
                    </>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* AI 활용 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">AI 활용</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                예측 · 분석 · 학습
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-base leading-[1.8] text-foreground">
              <p>
                본 플랫폼은 AI를 단순히 TCAD 결과를 빠르게 출력하는 수단으로만 활용하지 않습니다. 예측, 분석, 학습의 세 단계에서 서로 다른
                역할을 수행하도록 구성합니다.
              </p>
              <div className="flex flex-col gap-2">
                {AI_ROLES.map((role) => (
                  <p key={role.label}>
                    <span className="font-semibold text-foreground">{role.label}:</span> {role.body}
                  </p>
                ))}
              </div>
              <p>세 기능은 다음 과정이 연결되도록 지원합니다.</p>
              <FlowSteps
                steps={["조건 설정", "결과 예측", "변화 분석", "사용자 관찰", "이해 점검", "후속 실험"]}
              />
              <p>
                따라서 본 플랫폼에서 AI의 목적은 결과를 대신 판단하는 것이 아니라, 사용자가 MOSFET의 구조와 동작을 능동적으로 탐구할 수
                있도록 결과 생성과 학습 과정을 연결하는 데 있습니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* 주의사항 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">주의사항</h2>
          <Card className="border-accent-orange/40 bg-accent-orange/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-accent-orange">
                <AlertTriangle className="h-4 w-4" />
                교육용 도구 안내
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm leading-[1.8] text-foreground">
              <p>
                본 플랫폼은 MOSFET의 구조와 전기적 특성 사이의 관계를 학습하기 위한 교육용 도구입니다. 정밀한 소자 설계나 실제 공정 조건
                결정을 위한 상용 TCAD 대체 도구를 목적으로 하지 않습니다.
              </p>
              <p>
                예측 모델은 DEVSIM으로 생성된 데이터와 사전에 정의된 입력 범위를 기반으로 합니다. 따라서 학습 및 검증 범위를 벗어난
                조건에서는 예측 정확도가 낮아질 수 있으며, 입력 범위 내부의 결과도 실제 제작 소자 또는 다른 TCAD 환경의 결과와 차이가
                발생할 수 있습니다.
              </p>
              <p>
                또한 본 플랫폼의 시뮬레이션 조건에는 실제 소자 특성에 영향을 주는 모든 요소가 포함되어 있지 않습니다. 공정 변동성, 계면
                결함, 접촉 저항, 자가 발열, 양자 효과와 같은 일부 현상은 단순화되거나 제외될 수 있습니다.
              </p>
              <p>
                AI 해설은 입력 조건, 예측 결과와 분석 코드에서 계산된 정보를 기반으로 생성됩니다. 제공된 결과에서 확인할 수 없는 물리적
                원인을 임의로 단정하지 않도록 구성하지만, 해설은 학습을 돕기 위한 보조 자료로 활용해야 합니다.
              </p>
              <p className="mt-1 font-medium text-foreground">따라서 본 플랫폼의 결과는 다음 목적으로 활용하는 것이 적절합니다.</p>
              <ul className="list-inside list-disc space-y-0.5 pl-1">
                {APPROPRIATE_USES.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p className="mt-1">실제 소자 설계, 공정 최적화 또는 정밀한 성능 검증에는 별도의 TCAD 시뮬레이션과 실험적 검증이 필요합니다.</p>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
